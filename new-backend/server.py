"""
x402 + Flaunch API Integration
Wrap existing APIs with real token-based payments
"""

from flask import Flask, request, jsonify
import threading
import time
import requests
from typing import Dict, Optional
import json

app = Flask(__name__)

# Flaunch API Configuration
FLAUNCH_BASE_URL = "https://web2-api.flaunch.gg/api/v1"
FLAUNCH_DATA_API = "https://dev-api.flayerlabs.xyz/v1"
#NETWORK = "base-sepolia"  # Change to "base" for mainnet
NETWORK = "base"

class FlaunchTokenStore:
    def __init__(self):
        self.apis: Dict[str, dict] = {}
        self.launch_jobs: Dict[str, str] = {}
        self.price_sync_thread = None

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
            "marketCap": "10000000000",
            "creatorFeeSplit": "8000",
            "fairLaunchDuration": "1800",
            "sniperProtection": True
        }
        
        print(f"[FLAUNCH] Launching token for {api_name}...")
        print(f"[DEBUG] Payload: {json.dumps(launch_data)}") # DEBUG PRINT
        
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
                # RE-ADDED ERROR PRINTING SO WE CAN SEE THE ISSUE
                print(f"[FLAUNCH] ✗ API error: {response.status_code}")
                try:
                    print(f"[DEBUG] Server Response: {response.text}")
                except:
                    pass
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

            print("GETTING RESPONSE for job_id: " + job_id)
            print(response.json())
            
            return response.json()
            
        except Exception as e:
            print(f"[FLAUNCH] Error checking status: {str(e)}")
            return None
    
    def get_token_price_data(self, token_address: str) -> Optional[dict]:
        """Get real-time token price from Flaunch Data API"""
        try:
            response = requests.get(
                f"{FLAUNCH_DATA_API}/{NETWORK}/tokens/{token_address}/price",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "price_eth": float(data.get("price", {}).get("priceETH", 0)),
                    "market_cap_eth": float(data.get("price", {}).get("marketCapETH", 0)),
                    "price_change_24h": float(data.get("price", {}).get("priceChange24h", 0)),
                    "volume_24h": float(data.get("volume", {}).get("volume24h", 0)),
                    "all_time_high": float(data.get("price", {}).get("allTimeHigh", 0)),
                    "all_time_low": float(data.get("price", {}).get("allTimeLow", 0))
                }
            return None
            
        except Exception as e:
            print(f"[PRICE] Error fetching price: {str(e)}")
            return None
    
    def sync_prices(self):
        """Background thread to sync real token prices"""
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
                        
                        if old_price > 0:
                            change = ((new_price - old_price) / old_price * 100)
                            print(f"[PRICE] {api_config['symbol']}: {new_price:.8f} ETH ({change:+.2f}%)")
    
    def finalize_token_launch(self, endpoint: str):
        print(f"[DEBUGSHREY] FINALIZING TOKEN LAUNCH for {endpoint}")
        
        if endpoint not in self.apis:
            print("[DEBUGSHREY] Endpoint not found in store")
            return False
            
        api_config = self.apis[endpoint]
        job_id = api_config.get("job_id")
        
        # If we already have the address, we are done
        if api_config.get("token_address"):
            print("[DEBUGSHREY] Token address already known")
            return True
        
        if not job_id:
            print("[DEBUGSHREY] No Job ID found")
            return False
        
        status = self.check_launch_status(job_id)
        # print(f"[DEBUGSHREY] STATUS: {status}")
        
        # === CRITICAL FIX: Don't check for state == "completed" ===
        if status and status.get("success"):
            token_info = status.get("collectionToken", {})
            token_address = token_info.get("address")
            
            # If Flaunch gave us an address, IT IS LAUNCHED.
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
                
                print(f"[FLAUNCH] ✓ Token deployed at {token_address}")
                return True
            
        return False


store = FlaunchTokenStore()


def proxy_to_target_api(target_url: str, method: str = "GET"):
    """Proxy request to the wrapped API endpoint"""
    try:
        # Forward query params and body
        params = request.args.to_dict()
        data = request.get_json(silent=True)
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'x-payment']}
        
        if method.upper() == "GET":
            response = requests.get(target_url, params=params, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(target_url, json=data, params=params, headers=headers, timeout=30)
        else:
            return jsonify({"error": "Unsupported method"}), 400
        
        # Return the response from target API
        try:
            return jsonify(response.json()), response.status_code
        except:
            return response.text, response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({"error": "Target API timeout"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Target API error: {str(e)}"}), 502


def require_payment(endpoint: str):
    """Check payment based on REAL token price from Flaunch"""
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    
    # Check if token is deployed
    if not api_config.get("token_address"):
        return jsonify({
            "error": "Token still launching",
            "status": "Token deployment in progress. Please try again in a moment.",
            "job_id": api_config.get("job_id")
        }), 503
    
    price_eth = api_config.get("price_eth", 0.0001)
    payment_header = request.headers.get("X-PAYMENT")
    
    if not payment_header:
        return jsonify({
            "error": "Payment Required",
            "payment_details": {
                "endpoint": endpoint,
                "price_eth": f"{price_eth:.8f}",
                "price_data": api_config.get("price_data", {}),
                "token_address": api_config["token_address"],
                "token_symbol": api_config["symbol"],
                "pay_to_address": api_config["wallet_address"],
                "network": NETWORK,
                "chain_id": 84532 if NETWORK == "base-sepolia" else 8453,
                "view_token": f"https://flaunch.gg/token/{api_config['token_address']}",
                "description": f"Pay {price_eth:.8f} ETH worth of {api_config['symbol']} to access this API"
            }
        }), 402
    
    print(f"[PAYMENT] Received for {endpoint}: {price_eth:.8f} ETH")
    return None


@app.route("/<path:endpoint>", methods=["GET", "POST"])
def dynamic_api(endpoint):
    """Handle all dynamic API endpoints"""
    endpoint = "/" + endpoint
    
    # Try to finalize token if still pending
    if endpoint in store.apis:
        time.sleep(5)
        store.finalize_token_launch(endpoint)
    
    # Check payment
    payment_check = require_payment(endpoint)
    if payment_check:
        return payment_check
    
    # Payment verified, proxy to target API
    api_config = store.apis[endpoint]
    target_url = api_config["target_url"]
    method = api_config.get("method", "GET")
    
    return proxy_to_target_api(target_url, method)


@app.route("/admin/create-api", methods=["POST"])
def create_api():
    """
    Wrap an existing API with token-based payment
    
    Request body:
    {
        "name": "Weather API",
        "endpoint": "/weather",
        "target_url": "https://api.example.com/weather",
        "method": "GET",
        "wallet_address": "0xYourAddress",
        "description": "Get weather data"
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
    
    # Validate target URL
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
        "created_at": time.time()
    }
    
    # Launch real token on Flaunch
    launch_result = store.launch_token_on_flaunch(api_config)
    
    print(launch_result)

    if not launch_result:
        return jsonify({
            "error": "Failed to launch token on Flaunch"
        }), 500
    
    # Store job ID for tracking
    api_config["job_id"] = launch_result["jobId"]
    api_config["queue_position"] = launch_result.get("queueStatus", {}).get("position", 0)
    
    store.apis[endpoint] = api_config
    
    print(f"[API CREATED] {endpoint} -> {target_url}")
    print(f"[API CREATED] Token launching (Job: {api_config['job_id']})")
    
    # === THIS WAS MISSING ===
    # Wait 4 seconds for blockchain to catch up, then CALL FINALIZE
    print("[FLAUNCH] Waiting 4s for deployment...")
    time.sleep(4)
    store.finalize_token_launch(endpoint)
    # ========================

    return jsonify({
        "success": True,
        "api": {
            "name": data["name"],
            "endpoint": endpoint,
            "target_url": target_url,
            "method": api_config["method"],
            "wallet_address": data["wallet_address"],
            "launch_status": "pending",
            "job_id": api_config["job_id"],
            "queue_position": api_config["queue_position"],
            "check_status": f"GET /admin/api-status{endpoint}"
        },
        "message": "Token launch initiated. API will be active once token is deployed."
    }), 201


@app.route("/admin/api-status/<path:endpoint>", methods=["GET"])
def api_status(endpoint):
    """Check status of API and its token"""
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    
    # Try to update token status
    store.finalize_token_launch(endpoint)
    
    token_address = api_config.get("token_address")
    
    response = {
        "endpoint": endpoint,
        "name": api_config["name"],
        "target_url": api_config["target_url"],
        "method": api_config["method"],
        "status": "deployed" if token_address else "launching",
        "wallet_address": api_config["wallet_address"]
    }
    
    if token_address:
        response["token"] = {
            "address": token_address,
            "symbol": api_config.get("symbol"),
            "price_eth": api_config.get("price_eth"),
            "price_data": api_config.get("price_data"),
            "view_on_flaunch": f"https://flaunch.gg/token/{token_address}",
            "tx_hash": api_config.get("tx_hash")
        }
    else:
        response["token"] = {
            "status": "pending",
            "job_id": api_config.get("job_id")
        }
    
    return jsonify(response)


@app.route("/admin/token-price/<path:endpoint>", methods=["GET"])
def get_token_price(endpoint):
    """Get detailed price information for an API's token"""
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    token_address = api_config.get("token_address")
    
    if not token_address:
        return jsonify({
            "error": "Token not yet deployed",
            "status": "launching"
        }), 503
    
    # Fetch fresh price data
    price_data = store.get_token_price_data(token_address)
    
    if not price_data:
        return jsonify({
            "error": "Unable to fetch price data"
        }), 500
    
    return jsonify({
        "endpoint": endpoint,
        "token_address": token_address,
        "symbol": api_config["symbol"],
        "price_data": price_data,
        "api_cost_eth": price_data["price_eth"],
        "flaunch_link": f"https://flaunch.gg/token/{token_address}"
    })


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
            "wallet_address": api_config["wallet_address"]
        }
        
        if token_address:
            info["token"] = {
                "address": token_address,
                "symbol": api_config.get("symbol"),
                "price_eth": api_config.get("price_eth"),
                "view_on_flaunch": f"https://flaunch.gg/token/{token_address}"
            }
        
        apis_info.append(info)
    
    return jsonify({
        "total_apis": len(apis_info),
        "apis": apis_info
    })


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "message": "x402 + Flaunch: Wrap any API with token payments",
        "network": NETWORK,
        "chain_id": 84532 if NETWORK == "base-sepolia" else 8453,
        "endpoints": {
            "create_api": "POST /admin/create-api",
            "list_apis": "GET /admin/list-apis",
            "api_status": "GET /admin/api-status/<endpoint>",
            "token_price": "GET /admin/token-price/<endpoint>",
            "api_info": "GET /admin/api-info/<endpoint>  # Full price history + token info"
        },
        "active_apis": len(store.apis),
        "how_it_works": {
            "1": "POST to /admin/create-api with your existing API endpoint",
            "2": "Server launches a real token on Flaunch for that API",
            "3": "Token price from Flaunch = API access cost",
            "4": "Users pay with tokens to access your wrapped API"
        }
    })

@app.route("/admin/api-info/<path:endpoint>", methods=["GET"])
def get_api_info(endpoint):
    """
    Get comprehensive API information including price history, token address, and name
    
    Returns:
    - API name
    - Token contract address
    - Full price history (daily, hourly, minutely, secondly)
    - Current price data
    """
    endpoint = "/" + endpoint
    
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    token_address = api_config.get("token_address")
    
    if not token_address:
        return jsonify({
            "error": "Token not yet deployed",
            "status": "launching",
            "job_id": api_config.get("job_id"),
            "api_name": api_config["name"]
        }), 503
    
    # Fetch full price data with history from Flaunch Data API
    try:
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
        
        return jsonify({
            "api_name": api_config["name"],
            "token_address": token_address,
            "symbol": api_config.get("symbol"),
            "endpoint": endpoint,
            "target_url": api_config["target_url"],
            "method": api_config["method"],
            "current_price": {
                "price_eth": float(full_data.get("price", {}).get("priceETH", 0)),
                "market_cap_eth": float(full_data.get("price", {}).get("marketCapETH", 0)),
                "price_change_24h": float(full_data.get("price", {}).get("priceChange24h", 0)),
                "price_change_24h_percentage": float(full_data.get("price", {}).get("priceChange24hPercentage", 0)),
                "all_time_high": float(full_data.get("price", {}).get("allTimeHigh", 0)),
                "all_time_low": float(full_data.get("price", {}).get("allTimeLow", 0))
            },
            "volume": {
                "volume_24h": float(full_data.get("volume", {}).get("volume24h", 0)),
                "volume_7d": float(full_data.get("volume", {}).get("volume7d", 0))
            },
            "price_history": {
                "daily": full_data.get("priceHistory", {}).get("daily", []),
                "hourly": full_data.get("priceHistory", {}).get("hourly", []),
                "minutely": full_data.get("priceHistory", {}).get("minutely", []),
                "secondly": full_data.get("priceHistory", {}).get("secondly", [])
            },
            "trading": {
                "bid_wall_balance": float(full_data.get("trading", {}).get("bidWallBalance", 0)),
                "bid_wall_remaining": float(full_data.get("trading", {}).get("bidWallRemaining", 0)),
                "buyback_progress": float(full_data.get("trading", {}).get("buybackProgress", 0))
            },
            "links": {
                "flaunch": f"https://flaunch.gg/base/coin/{token_address}",
                "api_status": f"/admin/api-status{endpoint}"
            },
            "meta": full_data.get("meta", {})
        })
        
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Request timeout fetching price history",
            "api_name": api_config["name"],
            "token_address": token_address
        }), 504
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
    print(f"Network: {NETWORK}")
    print(f"Chain ID: {84532 if NETWORK == 'base-sepolia' else 8453}")
    print(f"\nWrap any existing API with token-based payments!")
    print(f"Real tokens launched on Flaunch, real prices from DEX")
    print(f"{'='*60}\n")
    
    app.run(debug=True, port=5000, use_reloader=True)