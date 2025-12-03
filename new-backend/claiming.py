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
from x402.flask.middleware import PaymentMiddleware

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
NETWORK = "base"  # Change to "base-sepolia" for testnet
FACILITATOR_URL = "https://x402.org/facilitator"  # For testnet

class FlaunchTokenStore:
    def __init__(self, preexisting_routes_file: Optional[str] = None):
        self.apis: Dict[str, dict] = {}
        self.launch_jobs: Dict[str, str] = {}
        self.price_sync_thread = None
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
                    "flaunch_link": route.get("flaunch_link", f"https://flaunch.gg/token/{route['token_address']}"),
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
                    print(f"       Token Price: ${token_price:.8f} USD | API Price: ${api_price:.6f} USD (x{price_multiplier})")
                    print(f"       Market Cap: ${price_data['market_cap_usd']:.2f} USD | 24h Volume: ${price_data['volume_24h_usd']:.2f} USD")
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

    def launch_token_on_flaunch(self, api_config: dict) -> dict:
        """Launch a real token on Flaunch for this API"""
        api_name = api_config["name"]
        symbol = api_name[:3].upper() + "API"
        
        SAFE_IMAGE_HASH = "QmX7UbPKJ7Drci3y6p6E8oi5TpUiG7NH3qSzcohPX9Xkvo"
        
        # Use standard starting market cap (in USD)
        # Lower market cap = more reasonable starting token price
        # Default: $10,000 - gives starting price around $0.0001
        starting_market_cap = api_config.get("starting_market_cap", "10000")
        
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
        
        Extracts actual USD prices from Flaunch API response.
        Returns token price in USD and API price (with multiplier applied).
        """
        try:
            response = requests.get(
                f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Method 1: Try to get from price history (most reliable - has priceUSDC)
                price_history = data.get("priceHistory", {})
                hourly_data = price_history.get("hourly", [])
                daily_data = price_history.get("daily", [])
                
                token_price_usd = 0
                volume_24h_usd = 0
                
                # Get most recent price from hourly data
                if hourly_data and len(hourly_data) > 0:
                    latest = hourly_data[-1]
                    token_price_usd = float(latest.get("priceUSDC") or latest.get("closeUSDC") or 0)
                    # Sum up 24h volume from hourly data
                    volume_24h_usd = sum(float(p.get("volumeUSDC", 0)) for p in hourly_data[-24:])
                elif daily_data and len(daily_data) > 0:
                    latest = daily_data[-1]
                    token_price_usd = float(latest.get("priceUSDC") or latest.get("closeUSDC") or 0)
                    volume_24h_usd = float(latest.get("volumeUSDC", 0))
                
                # Method 2: Fallback to price object (but check for USDC fields first)
                price_obj = data.get("price", {})
                if token_price_usd == 0:
                    # Try marketCapUSDC and derive price, or use priceETH as last resort
                    token_price_usd = float(price_obj.get("priceUSDC", 0))
                    if token_price_usd == 0:
                        # Last resort: use priceETH but it might actually be in USD
                        token_price_usd = float(price_obj.get("priceETH", 0))
                
                # Get market cap in USD (prefer marketCapUSDC)
                market_cap_usd = float(price_obj.get("marketCapUSDC", 0))
                if market_cap_usd == 0:
                    market_cap_usd = abs(float(price_obj.get("marketCapETH", 0)))
                
                # Get volume (fallback to volume object if not from history)
                if volume_24h_usd == 0:
                    volume_obj = data.get("volume", {})
                    volume_24h_usd = float(volume_obj.get("volume24hUSDC", 0))
                    if volume_24h_usd == 0:
                        volume_24h_usd = float(volume_obj.get("volume24h", 0))
                
                # All-time high/low
                all_time_high_usd = float(price_obj.get("allTimeHigh", 0))
                all_time_low_usd = float(price_obj.get("allTimeLow", 0))
                
                # Price change
                price_change_24h = float(price_obj.get("priceChange24h", 0))
                price_change_24h_pct = float(price_obj.get("priceChange24hPercentage", 0))
                
                print(f"[PRICE] Token: ${token_price_usd:.8f} USD, MCap: ${market_cap_usd:.2f}, Vol24h: ${volume_24h_usd:.2f}")
                
                return {
                    "token_price_usd": token_price_usd,  # Actual token price from Flaunch
                    "market_cap_usd": market_cap_usd,
                    "volume_24h_usd": volume_24h_usd,
                    "price_change_24h": price_change_24h,
                    "price_change_24h_percentage": price_change_24h_pct,
                    "all_time_high_usd": all_time_high_usd,
                    "all_time_low_usd": all_time_low_usd
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
            network="base-sepolia" if NETWORK == "base-sepolia" else "base"
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


@app.route("/<path:endpoint>", methods=["GET", "POST"])
def dynamic_api(endpoint):
    """
    Handle all dynamic API endpoints
    Payment is now handled by x402 middleware automatically
    """
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
        "starting_market_cap": data.get("starting_market_cap", "10000"),  # USD
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
        response["pricing"] = {
            "token_price_usd": token_price,
            "api_price_usd": api_price,
            "price_multiplier": price_multiplier,
            "transform_explanation": f"API users pay ${api_price:.6f} (token price ${token_price:.8f} x {price_multiplier})",
            "price_data": api_config.get("price_data")
        }
        response["payment_info"] = {
            "protocol": "x402",
            "currency": "USDC",
            "amount_per_call": f"${api_price:.6f}",
            "chain": "base" if NETWORK == "base" else "base-sepolia",
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
            info["token"] = {
                "address": token_address,
                "symbol": api_config.get("symbol"),
                "view_on_flaunch": f"https://flaunch.gg/base/coin/{token_address}"
            }
            info["pricing"] = {
                "token_price_usd": api_config.get("token_price_usd"),
                "api_price_usd": api_config.get("api_price_usd"),
                "price_multiplier": api_config.get("price_multiplier")
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
        "chain_id": 84532 if NETWORK == "base-sepolia" else 8453,
        "facilitator": FACILITATOR_URL,
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
        
        # Get volume data
        price_history_raw = full_data.get("priceHistory", {})
        daily_data = price_history_raw.get("daily", [])
        volume_7d_usd = sum(float(p.get("volumeUSDC", 0)) for p in daily_data) if daily_data else 0
        
        return jsonify({
            "api_name": api_config["name"],
            "token_address": token_address,
            "symbol": api_config.get("symbol"),
            "endpoint": endpoint,
            "target_url": api_config["target_url"],
            "method": api_config["method"],
            "description": api_config.get("description", ""),
            "input_format": api_config.get("input_format", {}),
            "output_format": api_config.get("output_format", {}),
            "schema_endpoint": f"/admin/api-schema{endpoint}",
            "payment_protocol": "x402",
            "x402_enabled": True,
            
            # Pricing Information - clearly separated
            "pricing": {
                "token_price_usd": token_price_usd,
                "api_price_usd": api_price_usd,
                "price_multiplier": price_multiplier,
                "transform_explanation": f"Token ${token_price_usd:.8f} USD x {price_multiplier} = API ${api_price_usd:.6f} USD per call"
            },
            
            # Market Data from Flaunch
            "market_data": {
                "market_cap_usd": price_data["market_cap_usd"],
                "volume_24h_usd": price_data["volume_24h_usd"],
                "volume_7d_usd": volume_7d_usd,
                "price_change_24h": price_data["price_change_24h"],
                "price_change_24h_percentage": price_data["price_change_24h_percentage"],
                "all_time_high_usd": price_data["all_time_high_usd"],
                "all_time_low_usd": price_data["all_time_low_usd"]
            },
            
            # Price History (raw from Flaunch)
            "price_history": {
                "note": "All prices in priceUSDC/closeUSDC fields are USD prices",
                "daily": full_data.get("priceHistory", {}).get("daily", []),
                "hourly": full_data.get("priceHistory", {}).get("hourly", []),
                "minutely": full_data.get("priceHistory", {}).get("minutely", []),
                "secondly": full_data.get("priceHistory", {}).get("secondly", [])
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
    print(f"Chain ID: {84532 if NETWORK == 'base-sepolia' else 8453}")
    print(f"Facilitator: {FACILITATOR_URL}")
    print(f"\nWrap any existing API with x402 token-based payments!")
    print(f"Real tokens launched on Flaunch, prices synced to x402")
    print(f"{'='*60}\n")
    
    app.run(debug=True, port=5000, use_reloader=True)