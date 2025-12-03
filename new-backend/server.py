"""
x402 + Flaunch API Integration
Dynamically-priced APIs tied to real token prices on Flaunch DEX

How it works:
1. Wrap any existing API endpoint with token-based pricing
2. Launch a real ERC-20 token on Flaunch for each API
3. API access cost = current token price from Flaunch (synced in real-time)
4. Users pay in USDC via x402 protocol, amount determined by token price
5. Token holders can trade on Flaunch while API pricing tracks market value

This creates dynamic, market-driven API pricing backed by tradeable tokens.
"""

from flask import Flask, request, jsonify
import threading
import time
import requests
from typing import Dict, Optional
import json
import os
from dotenv import load_dotenv
from x402.flask.middleware import PaymentMiddleware
from cdp.x402 import create_facilitator_config
try:
    from pydantic import ValidationError
except ImportError:
    try:
        from pydantic_core import ValidationError
    except ImportError:
        ValidationError = Exception

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Enable CORS for all routes
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Payment')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Payment')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

# Flaunch API Configuration
FLAUNCH_BASE_URL = "https://web2-api.flaunch.gg/api/v1"
FLAUNCH_DATA_API = "https://dev-api.flayerlabs.xyz/v1"
NETWORK = "base"  # Mainnet - using Base network for production

# CDP Facilitator Configuration for Mainnet
CDP_API_KEY_ID = os.getenv("CDP_API_KEY_ID")
CDP_API_KEY_SECRET = os.getenv("CDP_API_KEY_SECRET")

if not CDP_API_KEY_ID or not CDP_API_KEY_SECRET:
    raise ValueError(
        "CDP_API_KEY_ID and CDP_API_KEY_SECRET must be set in environment variables. "
        "Please add them to your .env file."
    )

# Create facilitator config for mainnet
facilitator_config = create_facilitator_config(
    api_key_id=CDP_API_KEY_ID,
    api_key_secret=CDP_API_KEY_SECRET,
)

class FlaunchTokenStore:
    def __init__(self, preexisting_routes_file: Optional[str] = None):
        self.apis: Dict[str, dict] = {}
        self.launch_jobs: Dict[str, str] = {}
        self.price_sync_thread = None
        # Initialize PaymentMiddleware (facilitator_config passed to add() method)
        self.payment_middleware = PaymentMiddleware(app)
        
        # Price multiplier to transform tiny token prices into reasonable API prices
        # Example: token price $0.000001 * 10000 = $0.01 API price
        self.default_price_multiplier = 10000  # Adjustable per API
        
        # Load pre-existing routes if file is provided
        if preexisting_routes_file is None:
            # Default to preexisting_routes.json in the same directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            preexisting_routes_file = os.path.join(script_dir, "preexisting_routes.json")
        
        self.load_preexisting_routes(preexisting_routes_file)
    
    def load_preexisting_routes(self, routes_file: str):
        """Load pre-existing API routes from a JSON file"""
        if not os.path.exists(routes_file):
            print(f"[INIT] No pre-existing routes file found at {routes_file}")
            return
        
        try:
            with open(routes_file, 'r') as f:
                routes = json.load(f)
            
            if not isinstance(routes, list):
                print(f"[INIT] Invalid format: routes file should contain a JSON array")
                return
            
            loaded_count = 0
            for route in routes:
                # Validate required fields
                required_fields = ["name", "endpoint", "target_url", "wallet_address", "token_address"]
                if not all(field in route for field in required_fields):
                    print(f"[INIT] Skipping route {route.get('name', 'unknown')}: missing required fields")
                    continue
                
                endpoint = route["endpoint"]
                if not endpoint.startswith("/"):
                    endpoint = "/" + endpoint
                
                # Skip if endpoint already exists
                if endpoint in self.apis:
                    print(f"[INIT] Skipping route {endpoint}: already exists")
                    continue
                
                # Create API config from pre-existing route
                api_config = {
                    "name": route["name"],
                    "endpoint": endpoint,
                    "target_url": route["target_url"],
                    "method": route.get("method", "GET").upper(),
                    "wallet_address": route["wallet_address"],
                    "description": route.get("description", ""),
                    "token_address": route["token_address"],
                    "symbol": route.get("symbol", route["name"][:3].upper() + "API"),
                    "token_uri": route.get("token_uri"),
                    "tx_hash": route.get("tx_hash"),
                    "flaunch_link": route.get("flaunch_link", f"https://flaunch.gg/base/coin/{route['token_address']}"),
                    "created_at": route.get("created_at", time.time()),
                    "preexisting": True  # Mark as pre-existing
                }
                
                # Set price multiplier (can be customized per API)
                price_multiplier = route.get("price_multiplier", self.default_price_multiplier)
                api_config["price_multiplier"] = price_multiplier
                
                # Fetch initial price data for the token
                price_data = self.get_token_price_data(route["token_address"])
                if price_data:
                    api_config["price_data"] = price_data
                    token_price = price_data["token_price_usd"]
                    api_price = token_price * price_multiplier
                    api_config["token_price_usd"] = token_price
                    api_config["api_price_usd"] = api_price
                    print(f"[INIT] Loaded {route['name']} ({endpoint})")
                    print(f"       Token: ${token_price:.8f} | API: ${api_price:.6f} (x{price_multiplier})")
                    print(f"       Vol 24h: ${price_data['volume_24h_usd']:.2f} | Vol 7d: ${price_data['volume_7d_usd']:.2f}")
                else:
                    # Use default price if unavailable
                    default_token_price = 0.000001
                    api_config["token_price_usd"] = default_token_price
                    api_config["api_price_usd"] = default_token_price * price_multiplier
                    print(f"[INIT] Loaded {route['name']} ({endpoint}) - Price data unavailable, using defaults")
                
                self.apis[endpoint] = api_config
                loaded_count += 1
            
            print(f"[INIT] Loaded {loaded_count} pre-existing API route(s)")
            
        except json.JSONDecodeError as e:
            print(f"[INIT] Error parsing JSON file {routes_file}: {str(e)}")
        except Exception as e:
            print(f"[INIT] Error loading pre-existing routes from {routes_file}: {str(e)}")
    
    def save_api_to_json(self, api_config: dict, routes_file: Optional[str] = None):
        """Save a new API to the preexisting_routes.json file"""
        if routes_file is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            routes_file = os.path.join(script_dir, "preexisting_routes.json")
        
        try:
            # Read existing routes
            routes = []
            if os.path.exists(routes_file):
                with open(routes_file, 'r') as f:
                    routes = json.load(f)
                    if not isinstance(routes, list):
                        routes = []
            
            # Check if this endpoint already exists in the file
            endpoint = api_config.get("endpoint", "")
            existing_index = None
            for i, route in enumerate(routes):
                if route.get("endpoint") == endpoint:
                    existing_index = i
                    break
            
            # Prepare the route data
            route_data = {
                "name": api_config.get("name", ""),
                "endpoint": endpoint,
                "target_url": api_config.get("target_url", ""),
                "method": api_config.get("method", "GET"),
                "wallet_address": api_config.get("wallet_address", ""),
                "description": api_config.get("description", ""),
                "token_address": api_config.get("token_address", ""),
                "symbol": api_config.get("symbol", ""),
                "token_uri": api_config.get("token_uri"),
                "tx_hash": api_config.get("tx_hash"),
                "flaunch_link": api_config.get("flaunch_link") or (f"https://flaunch.gg/base/coin/{api_config.get('token_address', '')}" if api_config.get("token_address") else None)
            }
            
            # Add optional fields if they exist
            if api_config.get("input_format"):
                route_data["input_format"] = api_config.get("input_format")
            if api_config.get("output_format"):
                route_data["output_format"] = api_config.get("output_format")
            if api_config.get("price_multiplier") and api_config.get("price_multiplier") != self.default_price_multiplier:
                route_data["price_multiplier"] = api_config.get("price_multiplier")
            
            # Remove None values
            route_data = {k: v for k, v in route_data.items() if v is not None}
            
            # Update existing or add new
            if existing_index is not None:
                routes[existing_index] = route_data
                print(f"[SAVE] Updated existing route in JSON: {endpoint}")
            else:
                routes.append(route_data)
                print(f"[SAVE] Added new route to JSON: {endpoint}")
            
            # Write back to file
            with open(routes_file, 'w') as f:
                json.dump(routes, f, indent=4)
                f.write('\n')  # Add newline at end of file
            
            print(f"[SAVE] Successfully saved {len(routes)} route(s) to {routes_file}")
            
        except Exception as e:
            print(f"[SAVE] Error saving route to JSON file {routes_file}: {str(e)}")

    def launch_token_on_flaunch(self, api_config: dict) -> dict:
        """Launch a real token on Flaunch for this API"""
        api_name = api_config["name"]
        symbol = api_name[:3].upper() + "API"
        
        SAFE_IMAGE_HASH = "QmX7UbPKJ7Drci3y6p6E8oi5TpUiG7NH3qSzcohPX9Xkvo"
        
        # Market cap in wei/smallest units (1M wei ≈ $1 USD)
        # Default: 1,000,000 wei ≈ $1 USD starting market cap
        starting_market_cap = api_config.get("starting_market_cap", "1000000")
        
        launch_data = {
            "name": f"{api_name} Token",
            "symbol": symbol,
            "description": f"Pay with {symbol} to access {api_name}. Token price = API access cost.",
            "imageIpfs": SAFE_IMAGE_HASH,
            "creatorAddress": api_config["wallet_address"],
            "marketCap": starting_market_cap,  # Market cap in USD
            "creatorFeeSplit": "8000",
            "fairLaunchDuration": "0",
            "sniperProtection": True
        }
        
        print(f"[FLAUNCH] Launching token for {api_name}...")
        
        try:
            response = requests.post(
                f"{FLAUNCH_BASE_URL}/{NETWORK}/launch-memecoin",
                json=launch_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"[FLAUNCH] ✓ Token launch queued! JobID: {result['jobId']}")
                    return result
                else:
                    print(f"[FLAUNCH] ✗ Launch failed: {result.get('error')}")
                    return None
            else:
                print(f"[FLAUNCH] ✗ API error: {response.status_code}")
                print(f"[DEBUG] Server Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"[FLAUNCH] ✗ Exception: {str(e)}")
            return None  
    
    def check_launch_status(self, job_id: str) -> Optional[dict]:
        """Check if token launch is complete"""
        try:
            response = requests.get(
                f"{FLAUNCH_BASE_URL}/launch-status/{job_id}",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            return response.json()
            
        except Exception as e:
            print(f"[FLAUNCH] Error checking status: {str(e)}")
            return None
    
    def get_token_price_data(self, token_address: str) -> Optional[dict]:
        """Get real-time token price from Flaunch Data API
        
        Returns only: priceUSDC, volumeUSDC24h, volumeUSDC7d
        """
        try:
            response = requests.get(
                f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Get priceUSDC directly from price object
                price_obj = data.get("price", {})
                token_price_usd = float(price_obj.get("priceUSDC", 0))
                
                # Get volumes from volume object
                volume_obj = data.get("volume", {})
                volume_24h_usd = float(volume_obj.get("volumeUSDC24h", 0))
                volume_7d_usd = float(volume_obj.get("volumeUSDC7d", 0))
                
                print(f"[PRICE] Token: ${token_price_usd:.8f} USD, Vol24h: ${volume_24h_usd:.2f}, Vol7d: ${volume_7d_usd:.2f}")
                
                return {
                    "token_price_usd": token_price_usd,
                    "volume_24h_usd": volume_24h_usd,
                    "volume_7d_usd": volume_7d_usd
                }
            return None
            
        except Exception as e:
            print(f"[PRICE] Error fetching price: {str(e)}")
            return None
    
    def sync_prices(self):
        """Background thread to sync real token prices and update x402 middleware"""
        while True:
            time.sleep(30)  # Check every 30 seconds
            
            for endpoint, api_config in self.apis.items():
                token_address = api_config.get("token_address")
                if token_address:
                    price_data = self.get_token_price_data(token_address)
                    
                    if price_data:
                        old_api_price = api_config.get("api_price_usd", 0)
                        
                        # Get token price and calculate API price
                        token_price = price_data["token_price_usd"]
                        price_multiplier = api_config.get("price_multiplier", self.default_price_multiplier)
                        new_api_price = token_price * price_multiplier
                        
                        # Update stored prices
                        api_config["price_data"] = price_data
                        api_config["token_price_usd"] = token_price
                        api_config["api_price_usd"] = new_api_price
                        
                        # Update x402 middleware with new API price
                        self.update_x402_route(endpoint, api_config)
                        
                        if old_api_price > 0:
                            change = ((new_api_price - old_api_price) / old_api_price * 100)
                            print(f"[SYNC] {api_config['symbol']}: Token ${token_price:.8f} -> API ${new_api_price:.6f} ({change:+.2f}%)")
    
    def update_x402_route(self, endpoint: str, api_config: dict):
        """Update or add x402 payment middleware for this route
        
        Uses the transformed API price (token_price * multiplier), not raw token price.
        """
        token_address = api_config.get("token_address")
        if not token_address:
            return
        
        # Get API price (transformed from token price)
        api_price_usd = api_config.get("api_price_usd", 0)
        token_price_usd = api_config.get("token_price_usd", 0)
        price_multiplier = api_config.get("price_multiplier", self.default_price_multiplier)
        
        # If no API price set, calculate from token price
        if api_price_usd <= 0:
            if token_price_usd > 0:
                api_price_usd = token_price_usd * price_multiplier
            else:
                api_price_usd = 0.001  # Fallback default
        
        # Format price for x402 (USDC amount)
        price_str = f"${api_price_usd:.6f}"
        
        # Add/update payment middleware for this route
        # x402 accepts USDC payment at the transformed API price
        self.payment_middleware.add(
            path=endpoint,
            price=price_str,
            pay_to_address=api_config["wallet_address"],
            network="base",  # Mainnet Base network
            facilitator_config=facilitator_config  # CDP facilitator for mainnet
        )
        
        symbol = api_config.get('symbol', 'token')
        print(f"[x402] Updated: {endpoint} -> {price_str}")
        print(f"       Token: ${token_price_usd:.8f} x {price_multiplier} = API Price: ${api_price_usd:.6f}")
    
    def finalize_token_launch(self, endpoint: str):
        if endpoint not in self.apis:
            return False
            
        api_config = self.apis[endpoint]
        job_id = api_config.get("job_id")
        
        if api_config.get("token_address"):
            return True
        
        if not job_id:
            return False
        
        status = self.check_launch_status(job_id)
        
        if status and status.get("success"):
            token_info = status.get("collectionToken") or {} 
            token_address = token_info.get("address")
            
            if token_address:
                api_config["token_address"] = token_address
                api_config["symbol"] = token_info.get("symbol")
                api_config["token_uri"] = token_info.get("tokenURI")
                api_config["tx_hash"] = status.get("transactionHash")
                
                # Ensure price multiplier is set
                if "price_multiplier" not in api_config:
                    api_config["price_multiplier"] = self.default_price_multiplier
                
                # Fetch initial price and calculate API price
                price_data = self.get_token_price_data(token_address)
                if price_data:
                    api_config["price_data"] = price_data
                    token_price = price_data["token_price_usd"]
                    api_price = token_price * api_config["price_multiplier"]
                    api_config["token_price_usd"] = token_price
                    api_config["api_price_usd"] = api_price
                    print(f"[FLAUNCH] ✓ Token deployed at {token_address}")
                    print(f"          Token: ${token_price:.8f} | API: ${api_price:.6f}")
                else:
                    # Set defaults if price fetch fails
                    api_config["token_price_usd"] = 0.000001
                    api_config["api_price_usd"] = 0.000001 * api_config["price_multiplier"]
                    print(f"[FLAUNCH] ✓ Token deployed at {token_address} (price data pending)")
                
                # Register with x402
                self.update_x402_route(endpoint, api_config)
                print(f"[x402] ✓ Payment route registered")
                
                # Update JSON file with token address now that it's deployed
                try:
                    self.save_api_to_json(api_config)
                except Exception as e:
                    print(f"[SAVE] Warning: Could not update JSON with token address: {str(e)}")
                
                return True
            
        return False

store = FlaunchTokenStore()


def proxy_to_target_api(target_url: str, method: str = "GET"):
    """Proxy request to the wrapped API endpoint"""
    try:
        params = request.args.to_dict()
        data = request.get_json(silent=True)
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'x-payment']}
        
        if method.upper() == "GET":
            response = requests.get(target_url, params=params, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(target_url, json=data, params=params, headers=headers, timeout=30)
        else:
            return jsonify({"error": "Unsupported method"}), 400
        
        try:
            return jsonify(response.json()), response.status_code
        except:
            return response.text, response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({"error": "Target API timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Target API error: {str(e)}"}), 502


@app.errorhandler(Exception)
def handle_x402_error(e):
    """Handle x402 middleware errors and other exceptions"""
    error_msg = str(e)
    error_type = str(type(e))
    
    # Check if this is a Pydantic validation error from x402
    is_validation_error = (
        isinstance(e, ValidationError) or 
        'ValidationError' in error_type or
        'pydantic' in error_type.lower()
    )
    
    if is_validation_error and ('payer' in error_msg.lower() or 'VerifyResponse' in error_msg):
        print(f"[x402 ERROR] Payment verification failed: {error_msg}")
        print(f"[x402 ERROR] Error type: {error_type}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Payment verification failed",
            "message": "The payment verification service encountered an error. Please ensure you're using the correct network (Base mainnet).",
            "details": "The facilitator may not support the requested network or the payment response was invalid.",
            "network": NETWORK,
            "facilitator": "CDP Facilitator (mainnet)",
            "error_type": error_type
        }), 500
    
    # For other exceptions, log and return generic error
    print(f"[ERROR] Unhandled exception: {error_msg}")
    print(f"[ERROR] Error type: {error_type}")
    import traceback
    traceback.print_exc()
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred while processing your request.",
        "error_type": error_type
    }), 500


@app.route("/<path:endpoint>", methods=["GET", "POST"])
def dynamic_api(endpoint):
    """
    Handle all dynamic API endpoints
    Payment is now handled by x402 middleware automatically
    """
    try:
        endpoint = "/" + endpoint
        
        # Try to finalize token if still pending
        if endpoint in store.apis:
            if not store.apis[endpoint].get("token_address"):
                time.sleep(5)
                if not store.finalize_token_launch(endpoint):
                    return jsonify({
                        "error": "Token still launching",
                        "status": "Token deployment in progress. Please try again in a moment.",
                        "job_id": store.apis[endpoint].get("job_id")
                    }), 503
        else:
            return jsonify({"error": "API endpoint not found"}), 404
        
        # If we reach here, x402 middleware has already verified payment
        # Proxy to target API
        api_config = store.apis[endpoint]
        target_url = api_config["target_url"]
        method = api_config.get("method", "GET")
        
        return proxy_to_target_api(target_url, method)
    except Exception as e:
        # Catch any exceptions that might occur during request processing
        print(f"[ERROR] Exception in dynamic_api: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Request processing failed",
            "message": str(e)
        }), 500


@app.route("/admin/create-api", methods=["POST"])
def create_api():
    """
    Wrap an existing API with x402 token-based payment
    
    Request body:
    {
        "name": "Weather API",
        "endpoint": "/weather",
        "target_url": "https://api.example.com/weather",
        "method": "GET",
        "wallet_address": "0xYourAddress",
        "description": "Get weather data",
        "input_format": {
            "query_params": {
                "city": {"type": "string", "required": true, "description": "City name"},
                "units": {"type": "string", "required": false, "default": "celsius", "description": "Temperature units"}
            },
            "body": null
        },
        "output_format": {
            "type": "object",
            "properties": {
                "temperature": {"type": "number", "description": "Temperature in specified units"},
                "condition": {"type": "string", "description": "Weather condition"},
                "humidity": {"type": "number", "description": "Humidity percentage"}
            }
        }
    }
    """
    data = request.json
    
    required_fields = ["name", "endpoint", "target_url", "wallet_address"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    endpoint = data["endpoint"]
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    
    if endpoint in store.apis:
        return jsonify({"error": "Endpoint already exists"}), 400
    
    target_url = data["target_url"]
    if not target_url.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid target URL"}), 400
    
    # Create API config
    api_config = {
        "name": data["name"],
        "endpoint": endpoint,
        "target_url": target_url,
        "method": data.get("method", "GET").upper(),
        "wallet_address": data["wallet_address"],
        "description": data.get("description", ""),
        "input_format": data.get("input_format", {}),
        "output_format": data.get("output_format", {}),
        "price_multiplier": data.get("price_multiplier", store.default_price_multiplier),
        "starting_market_cap": data.get("starting_market_cap", "1000000"),  # wei (1M wei ≈ $1)
        "created_at": time.time()
    }
    
    # Launch real token on Flaunch
    launch_result = store.launch_token_on_flaunch(api_config)

    if not launch_result:
        return jsonify({
            "error": "Failed to launch token on Flaunch"
        }), 500
    
    api_config["job_id"] = launch_result["jobId"]
    api_config["queue_position"] = launch_result.get("queueStatus", {}).get("position", 0)
    
    store.apis[endpoint] = api_config
    
    print(f"[API CREATED] {endpoint} -> {target_url}")
    print(f"[API CREATED] Token launching (Job: {api_config['job_id']})")
    
    # Poll for deployment
    print("[FLAUNCH] Polling for deployment completion...")
    
    timeout = 60
    start_time = time.time()
    deployed = False

    while time.time() - start_time < timeout:
        if store.finalize_token_launch(endpoint):
            deployed = True
            print(f"[FLAUNCH] ✓ Deployment confirmed in {int(time.time() - start_time)}s")
            break
        time.sleep(2)
        
    if not deployed:
        print("[FLAUNCH] ⚠ Deployment pending or taking longer than expected.")
    
    # Save API to JSON file for persistence
    # Save even if not fully deployed (will have job_id for later)
    try:
        store.save_api_to_json(api_config)
    except Exception as e:
        print(f"[SAVE] Warning: Could not save API to JSON: {str(e)}")

    response_data = {
        "success": True,
        "api": {
            "name": data["name"],
            "endpoint": endpoint,
            "target_url": target_url,
            "method": api_config["method"],
            "wallet_address": data["wallet_address"],
            "input_format": api_config.get("input_format", {}),
            "output_format": api_config.get("output_format", {}),
            "launch_status": "deployed" if deployed else "pending",
            "job_id": api_config["job_id"],
            "token_address": api_config.get("token_address"),
            "price_multiplier": api_config.get("price_multiplier"),
            "starting_market_cap": api_config.get("starting_market_cap"),
            "check_status": f"GET /admin/api-status{endpoint}",
            "view_schema": f"GET /admin/api-schema{endpoint}",
            "x402_enabled": deployed
        },
        "message": "Token launched and x402 payment enabled!" if deployed else "Token launch initiated."
    }
    
    # Add pricing info if deployed
    if deployed:
        response_data["pricing"] = {
            "token_price_usd": api_config.get("token_price_usd"),
            "api_price_usd": api_config.get("api_price_usd"),
            "transform": f"Token Price x {api_config.get('price_multiplier')} = API Price"
        }
    
    return jsonify(response_data), 201


@app.route("/admin/api-status/<path:endpoint>", methods=["GET"])
def api_status(endpoint):
    """Check status of API and its token"""
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    store.finalize_token_launch(endpoint)
    
    token_address = api_config.get("token_address")
    
    response = {
        "endpoint": endpoint,
        "name": api_config["name"],
        "target_url": api_config["target_url"],
        "method": api_config["method"],
        "status": "deployed" if token_address else "launching",
        "wallet_address": api_config["wallet_address"],
        "description": api_config.get("description", ""),
        "input_format": api_config.get("input_format", {}),
        "output_format": api_config.get("output_format", {}),
        "schema_endpoint": f"/admin/api-schema{endpoint}",
        "x402_enabled": bool(token_address)
    }
    
    if token_address:
        price_multiplier = api_config.get("price_multiplier", store.default_price_multiplier)
        token_price = api_config.get("token_price_usd", 0)
        api_price = api_config.get("api_price_usd", 0)
        
        response["token"] = {
            "address": token_address,
            "symbol": api_config.get("symbol"),
            "view_on_flaunch": f"https://flaunch.gg/base/coin/{token_address}",
            "tx_hash": api_config.get("tx_hash")
        }
        price_data = api_config.get("price_data", {})
        response["pricing"] = {
            "token_price_usd": token_price,
            "api_price_usd": api_price,
            "price_multiplier": price_multiplier,
            "volume_24h_usd": price_data.get("volume_24h_usd", 0),
            "volume_7d_usd": price_data.get("volume_7d_usd", 0)
        }
        response["payment_info"] = {
            "protocol": "x402",
            "currency": "USDC",
            "amount_per_call": f"${api_price:.6f}",
            "chain": "base",  # Mainnet Base network
            "price_updates": "Real-time from Flaunch DEX (with multiplier transform)"
        }
    else:
        response["token"] = {
            "status": "pending",
            "job_id": api_config.get("job_id")
        }
    
    return jsonify(response)


@app.route("/admin/api-schema/<path:endpoint>", methods=["GET"])
def get_api_schema(endpoint):
    """
    Get the input and output format schema for an API endpoint
    
    Returns detailed schema information that can be used to:
    - Understand what inputs the API expects
    - Understand what outputs the API returns
    - Generate API client code
    - Validate requests before sending
    """
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    
    schema = {
        "endpoint": endpoint,
        "name": api_config["name"],
        "method": api_config["method"],
        "description": api_config.get("description", ""),
        "input_format": api_config.get("input_format", {}),
        "output_format": api_config.get("output_format", {}),
        "example_request": {},
        "example_response": {}
    }
    
    # Generate example request based on input_format
    input_format = api_config.get("input_format", {})
    if input_format:
        example_request = {}
        
        # Handle query parameters
        if "query_params" in input_format:
            example_request["query_params"] = {}
            for param, spec in input_format["query_params"].items():
                if spec.get("required", False):
                    example_type = spec.get("type", "string")
                    if example_type == "string":
                        example_request["query_params"][param] = f"example_{param}"
                    elif example_type == "number":
                        example_request["query_params"][param] = 0
                    elif example_type == "boolean":
                        example_request["query_params"][param] = True
                    else:
                        example_request["query_params"][param] = None
                elif "default" in spec:
                    example_request["query_params"][param] = spec["default"]
        
        # Handle request body
        if "body" in input_format and input_format["body"]:
            if isinstance(input_format["body"], dict):
                example_request["body"] = input_format["body"]
            else:
                example_request["body"] = {}
        
        schema["example_request"] = example_request
    
    # Generate example response based on output_format
    output_format = api_config.get("output_format", {})
    if output_format:
        if isinstance(output_format, dict) and "properties" in output_format:
            example_response = {}
            for prop, spec in output_format["properties"].items():
                prop_type = spec.get("type", "string")
                if prop_type == "string":
                    example_response[prop] = f"example_{prop}"
                elif prop_type == "number":
                    example_response[prop] = 0
                elif prop_type == "boolean":
                    example_response[prop] = True
                elif prop_type == "array":
                    example_response[prop] = []
                elif prop_type == "object":
                    example_response[prop] = {}
                else:
                    example_response[prop] = None
            schema["example_response"] = example_response
        else:
            schema["example_response"] = output_format
    
    # Add usage instructions
    schema["usage"] = {
        "curl_example": f"curl -X {api_config['method']} http://localhost:5000{endpoint}",
        "with_payment": "Include X-PAYMENT header for authenticated requests",
        "view_full_info": f"/admin/api-info{endpoint}",
        "view_status": f"/admin/api-status{endpoint}"
    }
    
    return jsonify(schema)


@app.route("/admin/list-apis", methods=["GET"])
def list_apis():
    """List all APIs and their token status"""
    apis_info = []
    for endpoint, api_config in store.apis.items():
        token_address = api_config.get("token_address")
        info = {
            "name": api_config["name"],
            "endpoint": endpoint,
            "target_url": api_config["target_url"],
            "method": api_config["method"],
            "status": "deployed" if token_address else "launching",
            "wallet_address": api_config["wallet_address"],
            "description": api_config.get("description", ""),
            "has_input_format": bool(api_config.get("input_format")),
            "has_output_format": bool(api_config.get("output_format")),
            "schema_endpoint": f"/admin/api-schema{endpoint}",
            "x402_enabled": bool(token_address)
        }
        
        if token_address:
            price_data = api_config.get("price_data", {})
            info["token"] = {
                "address": token_address,
                "symbol": api_config.get("symbol"),
                "view_on_flaunch": f"https://flaunch.gg/base/coin/{token_address}"
            }
            info["pricing"] = {
                "token_price_usd": api_config.get("token_price_usd"),
                "api_price_usd": api_config.get("api_price_usd"),
                "price_multiplier": api_config.get("price_multiplier"),
                "volume_24h_usd": price_data.get("volume_24h_usd", 0),
                "volume_7d_usd": price_data.get("volume_7d_usd", 0)
            }
        
        apis_info.append(info)
    
    return jsonify({
        "total_apis": len(apis_info),
        "apis": apis_info,
        "protocol": "x402",
        "network": NETWORK
    })


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "message": "x402 + Flaunch: Wrap any API with token payments",
        "protocol": "x402",
        "network": NETWORK,
        "chain_id": 8453,  # Base mainnet chain ID
        "facilitator": "CDP Facilitator (mainnet)",
        "endpoints": {
            "create_api": "POST /admin/create-api",
            "list_apis": "GET /admin/list-apis",
            "api_status": "GET /admin/api-status/<endpoint>",
            "api_schema": "GET /admin/api-schema/<endpoint>  # View input/output formats",
            "api_info": "GET /admin/api-info/<endpoint>"
        },
        "active_apis": len(store.apis),
        "how_it_works": {
            "1": "POST to /admin/create-api with your existing API endpoint",
            "2": "Server launches a real token on Flaunch for that API",
            "3": "Token price from Flaunch is transformed (multiplied) to create API price",
            "4": "x402 protocol enforces USDC payments at the transformed API price",
            "5": "API price updates in real-time as token trades on Flaunch"
        },
        "pricing_system": {
            "token_price": "Actual market price from Flaunch DEX (usually tiny, e.g. $0.000001)",
            "price_multiplier": f"Default {store.default_price_multiplier}x (customizable per API)",
            "api_price": "Token price × multiplier = reasonable API cost ($0.0001 - $0.01)",
            "example": f"Token $0.000001 × {store.default_price_multiplier} = API $0.01 per call"
        }
    })


@app.route("/admin/api-info/<path:endpoint>", methods=["GET"])
def get_api_info(endpoint):
    """Get comprehensive API information including price history and market data"""
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    token_address = api_config.get("token_address")
    
    if not token_address:
        print("TOKEN NOT YET DEPLOYED")
        return jsonify({
            "error": "Token not yet deployed",
            "status": "launching",
            "job_id": api_config.get("job_id"),
            "api_name": api_config["name"]
        }), 503
    
    try:
        # Fetch fresh price data and history from Flaunch
        response = requests.get(
            f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({
                "error": "Unable to fetch price data from Flaunch",
                "api_name": api_config["name"],
                "token_address": token_address
            }), 500
        
        full_data = response.json()
        
        # Parse using our improved get_token_price_data logic
        price_data = store.get_token_price_data(token_address)
        
        if not price_data:
            return jsonify({
                "error": "Unable to parse price data",
                "api_name": api_config["name"],
                "token_address": token_address
            }), 500
        
        # Calculate API price from token price
        token_price_usd = price_data["token_price_usd"]
        price_multiplier = api_config.get("price_multiplier", store.default_price_multiplier)
        api_price_usd = token_price_usd * price_multiplier
        
        return jsonify({
            "api_name": api_config["name"],
            "token_address": token_address,
            "symbol": api_config.get("symbol"),
            "endpoint": endpoint,
            "target_url": api_config["target_url"],
            "method": api_config["method"],
            "description": api_config.get("description", ""),
            "payment_protocol": "x402",
            "x402_enabled": True,
            
            # Pricing Information
            "pricing": {
                "token_price_usd": token_price_usd,
                "api_price_usd": api_price_usd,
                "price_multiplier": price_multiplier,
                "volume_24h_usd": price_data["volume_24h_usd"],
                "volume_7d_usd": price_data["volume_7d_usd"]
            },
            
            # Links
            "links": {
                "flaunch": f"https://flaunch.gg/base/coin/{token_address}",
                "api_status": f"/admin/api-status{endpoint}"
            }
        })
        
    except Exception as e:
        import traceback
        print(f"[ERROR] get_api_info exception: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "error": f"Error fetching price data: {str(e)}",
            "api_name": api_config["name"],
            "token_address": token_address
        }), 500

@app.route("/admin/checkjobid", methods=["GET"])
def check_jobid():
    job_id = request.json.get("job_id")
    print("CHECKING JOB ID: " + job_id)
    return jsonify(store.check_launch_status(job_id))

if __name__ == "__main__":
    # Start price sync thread
    price_thread = threading.Thread(target=store.sync_prices, daemon=True)
    price_thread.start()
    
    print(f"\n{'='*60}")
    print(f"x402 + Flaunch API Server")
    print(f"{'='*60}")
    print(f"Protocol: x402")
    print(f"Network: {NETWORK}")
    print(f"Chain ID: 8453 (Base mainnet)")
    print(f"Facilitator: CDP Facilitator (mainnet)")
    print(f"\nWrap any existing API with x402 token-based payments!")
    print(f"Real tokens launched on Flaunch, prices synced to x402")
    print(f"{'='*60}\n")
    
    app.run(debug=True, port=5000, use_reloader=True)