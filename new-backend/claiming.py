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
                
                # Fetch initial price data for the token
                price_data = self.get_token_price_data(route["token_address"])
                if price_data:
                    api_config["price_data"] = price_data
                    api_config["price_usd"] = price_data["price_usd"]
                    api_config["price_eth"] = price_data["price_eth"]
                    print(f"[INIT] Loaded {route['name']} ({endpoint}) - Price: ${price_data['price_usd']:.6f} USD ({price_data['price_eth']:.8f} ETH)")
                else:
                    # Use default price if unavailable
                    default_price_usd = route.get("price_usd", 0.01)
                    api_config["price_usd"] = default_price_usd
                    api_config["price_eth"] = default_price_usd / 3000  # Approximate conversion
                    print(f"[INIT] Loaded {route['name']} ({endpoint}) - Price data unavailable, using default ${default_price_usd:.6f} USD")
                
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
        
        launch_data = {
            "name": f"{api_name} Token",
            "symbol": symbol,
            "description": f"Pay with {symbol} to access {api_name}. Token price = API access cost.",
            "imageIpfs": SAFE_IMAGE_HASH,
            "creatorAddress": api_config["wallet_address"],
            "marketCap": "1000000",
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
        Note: Flaunch API returns prices in USD/USDC (field name "priceETH" is misleading)
        """
        try:
            response = requests.get(
                f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Flaunch API returns prices in USD/USDC (despite confusing field name "priceETH")
                # Store USD prices directly for x402 middleware
                eth_price_usd = 3000  # Approximate ETH price in USD
                
                price_usd = float(data.get("price", {}).get("priceETH", 0))
                market_cap_usd = float(data.get("price", {}).get("marketCapETH", 0))
                all_time_high_usd = float(data.get("price", {}).get("allTimeHigh", 0))
                all_time_low_usd = float(data.get("price", {}).get("allTimeLow", 0))
                
                # Convert from USD to ETH only for display purposes
                price_eth = price_usd / eth_price_usd if eth_price_usd > 0 else 0
                market_cap_eth = market_cap_usd / eth_price_usd if eth_price_usd > 0 else 0
                all_time_high_eth = all_time_high_usd / eth_price_usd if eth_price_usd > 0 else 0
                all_time_low_eth = all_time_low_usd / eth_price_usd if eth_price_usd > 0 else 0
                
                return {
                    "price_usd": price_usd,  # Store USD price directly
                    "price_eth": price_eth,  # Also store ETH for display
                    "market_cap_usd": market_cap_usd,
                    "market_cap_eth": market_cap_eth,
                    "price_change_24h": float(data.get("price", {}).get("priceChange24h", 0)),
                    "volume_24h": float(data.get("volume", {}).get("volume24h", 0)),
                    "all_time_high": all_time_high_eth,
                    "all_time_low": all_time_low_eth
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
                        old_price = api_config.get("price_eth", 0)
                        new_price = price_data["price_eth"]
                        
                        api_config["price_data"] = price_data
                        api_config["price_eth"] = new_price
                        
                        # Update x402 middleware with new price
                        self.update_x402_route(endpoint, api_config)
                        
                        if old_price > 0:
                            change = ((new_price - old_price) / old_price * 100)
                            print(f"[PRICE] {api_config['symbol']}: {new_price:.8f} ETH ({change:+.2f}%)")
    
    def update_x402_route(self, endpoint: str, api_config: dict):
        """Update or add x402 payment middleware for this route"""
        token_address = api_config.get("token_address")
        if not token_address:
            return
        
        # Get USD price directly from price_data (Flaunch API returns prices in USD)
        price_data = api_config.get("price_data", {})
        price_usd = price_data.get("price_usd", 0)
        
        if price_usd <= 0:
            # Fallback to old method if price_data not available
            price_eth = api_config.get("price_eth", 0.0001)
            eth_to_usd = 3000
            price_usd = price_eth * eth_to_usd
        
        price_str = f"${price_usd:.6f}"
        
        # Add/update payment middleware for this route
        # Note: x402 accepts USDC payment, amount is based on Flaunch token price in USD
        self.payment_middleware.add(
            path=endpoint,
            price=price_str,
            pay_to_address=api_config["wallet_address"],
            network="base-sepolia" if NETWORK == "base-sepolia" else "base"
        )
        
        price_eth_display = price_data.get("price_eth", price_usd / 3000)
        print(f"[x402] Updated payment route: {endpoint} -> {price_str} (based on ${price_usd:.2f} price of {api_config.get('symbol', 'token')})")
    
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
                
                # Fetch initial price
                price_data = self.get_token_price_data(token_address)
                if price_data:
                    api_config["price_data"] = price_data
                    api_config["price_eth"] = price_data["price_eth"]
                
                # Register with x402
                self.update_x402_route(endpoint, api_config)
                
                print(f"[FLAUNCH] ✓ Token deployed at {token_address}")
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

    return jsonify({
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
            "check_status": f"GET /admin/api-status{endpoint}",
            "view_schema": f"GET /admin/api-schema{endpoint}",
            "x402_enabled": deployed
        },
        "message": "Token launched and x402 payment enabled!" if deployed else "Token launch initiated."
    }), 201


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
        response["token"] = {
            "address": token_address,
            "symbol": api_config.get("symbol"),
            "price_eth": api_config.get("price_eth"),
            "price_data": api_config.get("price_data"),
            "view_on_flaunch": f"https://flaunch.gg/base/coin/{token_address}",
            "tx_hash": api_config.get("tx_hash")
        }
        response["payment_info"] = {
            "protocol": "x402",
            "accepts": api_config.get("symbol"),
            "chain": "base" if NETWORK == "base" else "base-sepolia",
            "price_updates": "Real-time from Flaunch DEX"
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
                "price_eth": api_config.get("price_eth"),
                "view_on_flaunch": f"https://flaunch.gg/base/coin/{token_address}"
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
            "3": "x402 protocol enforces payments using the token",
            "4": "Token price from Flaunch = API access cost (updates in real-time)",
            "5": "Users pay with tokens via x402 standard to access your API"
        }
    })


@app.route("/admin/api-info/<path:endpoint>", methods=["GET"])
def get_api_info(endpoint):
    """Get comprehensive API information including price history"""
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
        # Try to fetch price data - the API might support query parameters for more history
        # Based on the meta.timeRanges field, we can see what ranges are available
        response = requests.get(
            f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({
                "error": "Unable to fetch price history",
                "api_name": api_config["name"],
                "token_address": token_address
            }), 500
        
        full_data = response.json()
        
        # Check meta.timeRanges to see what data is available
        meta = full_data.get("meta", {})
        time_ranges = meta.get("timeRanges", {})
        print(f"[DEBUG] Available time ranges: {time_ranges}")
        
        # Note: The Flaunch API appears to only return recent data by default
        # There don't seem to be query parameters for date ranges in the documentation
        # The API returns what it has available, which may be limited for newer tokens
        
        # Debug: Log price history structure
        price_history_raw = full_data.get("priceHistory", {})
        print(f"[DEBUG] Price history type: {type(price_history_raw)}")
        print(f"[DEBUG] Price history keys: {list(price_history_raw.keys()) if isinstance(price_history_raw, dict) else 'Not a dict'}")
        if isinstance(price_history_raw, dict):
            for key in ["daily", "hourly", "minutely", "secondly"]:
                data = price_history_raw.get(key, [])
                print(f"[DEBUG] {key}: {len(data) if isinstance(data, list) else 'not a list'} items")
                if isinstance(data, list) and len(data) > 0:
                    print(f"[DEBUG] First {key} item sample: {data[0]}")
        
        # Flaunch API returns prices - extract from correct fields
        # The API has priceUSDC in price history, and priceETH in main price object (but priceETH is misleading)
        # Try to get current price from most recent price history point, or use price object fields
        
        # Get price from most recent hourly/daily data point (most reliable)
        price_usd = 0
        market_cap_usd = 0
        volume_24h = 0
        
        # Try to get from most recent price history point
        hourly_data = price_history_raw.get("hourly", [])
        daily_data = price_history_raw.get("daily", [])
        
        if hourly_data and len(hourly_data) > 0:
            latest_point = hourly_data[-1]
            price_usd = float(latest_point.get("priceUSDC") or latest_point.get("closeUSDC") or 0)
            # Sum up volumeUSDC from all hourly points for 24h volume
            volume_24h = sum(float(p.get("volumeUSDC", 0)) for p in hourly_data)
        elif daily_data and len(daily_data) > 0:
            latest_point = daily_data[-1]
            price_usd = float(latest_point.get("priceUSDC") or latest_point.get("closeUSDC") or 0)
            # Use volumeUSDC from most recent daily point
            volume_24h = float(latest_point.get("volumeUSDC", 0))
        
        # Fallback: try price object (but these fields might be in wrong units)
        if price_usd == 0:
            price_obj = full_data.get("price", {})
            # Try priceETH - but it might need conversion
            raw_price = float(price_obj.get("priceETH", 0))
            if raw_price > 0 and raw_price < 1:  # If it's already a reasonable price
                price_usd = raw_price
            elif raw_price > 1e15:  # If it's in wei or smallest unit
                price_usd = raw_price / 1e18
            else:
                price_usd = raw_price
        
        # Get market cap from main price object - use marketCapUSDC (in USD) instead of marketCapETH
        price_obj = full_data.get("price", {})
        print(f"[DEBUG] Price object keys: {list(price_obj.keys())}")
        print(f"[DEBUG] marketCapUSDC raw: {price_obj.get('marketCapUSDC')}")
        print(f"[DEBUG] marketCapETH raw: {price_obj.get('marketCapETH')}")
        
        # Use marketCapUSDC first (it's in USD/USDC) - this is the correct field
        market_cap_usd = float(price_obj.get("marketCapUSDC", 0))
        
        # If marketCapUSDC is not available or invalid, try marketCapETH as fallback
        if market_cap_usd <= 0:
            raw_mcap_eth = float(price_obj.get("marketCapETH", 0))
            # If it's negative, take absolute value
            if raw_mcap_eth < 0:
                raw_mcap_eth = abs(raw_mcap_eth)
            # marketCapETH might be in smallest units or need conversion
            # But since it's often wrong, prefer marketCapUSDC
            if raw_mcap_eth > 1e15:
                # Try converting from smallest units
                market_cap_usd = raw_mcap_eth / 1e18
            elif raw_mcap_eth > 0 and raw_mcap_eth < 1e15:
                market_cap_usd = raw_mcap_eth
        
        # Ensure market cap is positive
        if market_cap_usd < 0:
            market_cap_usd = abs(market_cap_usd)
        
        # If still no volume, try from main volume object (but it might be in wrong units)
        if volume_24h == 0:
            volume_obj = full_data.get("volume", {})
            raw_volume = float(volume_obj.get("volume24h", 0))
            # If volume is unreasonably large, it might be in smallest units
            if raw_volume > 1e15:
                volume_24h = raw_volume / 1e18
            elif raw_volume > 0 and raw_volume < 1e10:  # Reasonable range
                volume_24h = raw_volume
        
        # Get 7d volume
        volume_7d = 0
        if daily_data and len(daily_data) > 0:
            # Sum volumeUSDC from all daily points
            volume_7d = sum(float(p.get("volumeUSDC", 0)) for p in daily_data)
        
        if volume_7d == 0:
            volume_obj = full_data.get("volume", {})
            raw_volume_7d = float(volume_obj.get("volume7d", 0))
            if raw_volume_7d > 1e15:
                volume_7d = raw_volume_7d / 1e18
            elif raw_volume_7d > 0 and raw_volume_7d < 1e10:
                volume_7d = raw_volume_7d
        
        # All time high/low
        all_time_high_usd = float(full_data.get("price", {}).get("allTimeHigh", 0))
        all_time_low_usd = float(full_data.get("price", {}).get("allTimeLow", 0))
        
        # Convert to ETH if needed (for reference)
        eth_price_usd = 3000  # Approximate
        price_eth = price_usd / eth_price_usd if eth_price_usd > 0 else 0
        market_cap_eth = market_cap_usd / eth_price_usd if eth_price_usd > 0 else 0
        all_time_high_eth = all_time_high_usd / eth_price_usd if eth_price_usd > 0 else 0
        all_time_low_eth = all_time_low_usd / eth_price_usd if eth_price_usd > 0 else 0
        
        print(f"[DEBUG] Extracted price_usd: {price_usd}, market_cap_usd: {market_cap_usd}, volume_24h: {volume_24h}")
        
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
            "current_price": {
                "price_usd": price_usd,  # Primary price in USD (what x402 uses)
                "price_eth": price_eth,  # Also show in ETH for reference
                "market_cap_usd": market_cap_usd,
                "market_cap_eth": market_cap_eth,
                "price_change_24h": float(full_data.get("price", {}).get("priceChange24h", 0)),
                "price_change_24h_percentage": float(full_data.get("price", {}).get("priceChange24hPercentage", 0)),
                "all_time_high": all_time_high_eth,
                "all_time_low": all_time_low_eth
            },
            "volume": {
                "volume_24h": volume_24h,
                "volume_7d": volume_7d
            },
            "price_history": {
                "daily": full_data.get("priceHistory", {}).get("daily", []),
                "hourly": full_data.get("priceHistory", {}).get("hourly", []),
                "minutely": full_data.get("priceHistory", {}).get("minutely", []),
                "secondly": full_data.get("priceHistory", {}).get("secondly", [])
            },
            "links": {
                "flaunch": f"https://flaunch.gg/base/coin/{token_address}",
                "api_status": f"/admin/api-status{endpoint}"
            }
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Error fetching price history: {str(e)}",
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