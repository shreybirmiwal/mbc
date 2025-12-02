"""
x402 Dynamic API Server with Token-Based Pricing

This server demonstrates:
1. Creating APIs dynamically at runtime
2. Each API gets its own token with dynamic pricing
3. Price updates automatically based on token value
"""

from flask import Flask, request, jsonify
import threading
import time
import random
from typing import Dict, Callable

app = Flask(__name__)

# Store for dynamic routes and their tokens
class TokenStore:
    def __init__(self):
        self.tokens: Dict[str, dict] = {}
        self.apis: Dict[str, dict] = {}
        self.price_update_thread = None
        
    def create_token(self, api_name: str) -> str:
        token_id = f"TOKEN_{api_name.upper().replace(' ', '_')}"
        self.tokens[token_id] = {
            "id": token_id,
            "name": f"{api_name} Token",
            "symbol": api_name[:3].upper() + "T",
            "price_usd": round(random.uniform(0.001, 0.01), 6),
            "volatility": random.uniform(0.05, 0.15)  # 5-15% price changes
        }
        return token_id
    
    def get_price(self, token_id: str) -> float:
        """Get current price in USD"""
        if token_id in self.tokens:
            return self.tokens[token_id]["price_usd"]
        return 0.001
    
    def update_prices(self):
        """Simulate price updates (runs in background)"""
        while True:
            time.sleep(5)  # Update every 5 seconds
            for token_id, token in self.tokens.items():
                # Simulate price volatility
                change = random.uniform(-token["volatility"], token["volatility"])
                new_price = token["price_usd"] * (1 + change)
                # Keep price above minimum
                token["price_usd"] = max(0.0001, round(new_price, 6))
                print(f"[PRICE UPDATE] {token['symbol']}: ${token['price_usd']:.6f}")

store = TokenStore()

# Predefined handlers
def weather_handler():
    return jsonify({
        "weather": "sunny",
        "temperature": 72,
        "location": "San Francisco"
    })

def random_number_handler():
    return jsonify({
        "number": random.randint(1, 100)
    })

def default_handler(endpoint):
    return jsonify({
        "message": "API response",
        "endpoint": endpoint,
        "timestamp": time.time()
    })

HANDLERS = {
    "weather_data": weather_handler,
    "random_number": random_number_handler,
    "default": default_handler
}


def require_payment(endpoint: str):
    """Check payment based on current token price"""
    if endpoint not in store.apis:
        return jsonify({"error": "API not found"}), 404
    
    api_config = store.apis[endpoint]
    token_id = api_config["token_id"]
    current_price = store.get_price(token_id)
    
    # Check for payment header
    payment_header = request.headers.get("X-PAYMENT")
    
    if not payment_header:
        # Return 402 with payment requirements
        return jsonify({
            "error": "Payment Required",
            "payment_details": {
                "endpoint": endpoint,
                "price_usd": f"${current_price:.6f}",
                "token": store.tokens[token_id]["symbol"],
                "token_id": token_id,
                "pay_to_address": api_config["wallet_address"],
                "network": "base-sepolia",
                "facilitator": "https://x402.org/facilitator",
                "description": api_config.get("description", "API access")
            }
        }), 402
    
    # In real implementation, verify payment here
    # For demo, we just check if header exists
    print(f"[PAYMENT] Received payment for {endpoint}: ${current_price:.6f}")
    return None  # Payment verified


# Dynamic catch-all route
@app.route("/<path:endpoint>", methods=["GET", "POST"])
def dynamic_api(endpoint):
    """Handle all dynamic API endpoints"""
    endpoint = "/" + endpoint
    
    # Check payment first
    payment_check = require_payment(endpoint)
    if payment_check:
        return payment_check
    
    # Payment verified, execute handler
    api_config = store.apis[endpoint]
    handler_type = api_config.get("handler", "default")
    handler = HANDLERS.get(handler_type, HANDLERS["default"])
    
    # Call handler (pass endpoint for default handler)
    if handler_type == "default":
        return handler(endpoint)
    else:
        return handler()


# Admin endpoint to create new APIs dynamically
@app.route("/admin/create-api", methods=["POST"])
def create_api():
    """
    Create a new API endpoint with its own token and dynamic pricing
    
    Request body:
    {
        "name": "Weather API",
        "endpoint": "/weather",
        "wallet_address": "0xYourAddress",
        "description": "Get weather data",
        "handler": "weather_data"  # predefined handler
    }
    """
    data = request.json
    
    required_fields = ["name", "endpoint", "wallet_address"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    endpoint = data["endpoint"]
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    
    # Check if endpoint already exists
    if endpoint in store.apis:
        return jsonify({"error": "Endpoint already exists"}), 400
    
    # Create token for this API
    token_id = store.create_token(data["name"])
    
    # Store API configuration
    store.apis[endpoint] = {
        "name": data["name"],
        "endpoint": endpoint,
        "token_id": token_id,
        "wallet_address": data["wallet_address"],
        "description": data.get("description", ""),
        "handler": data.get("handler", "default")
    }
    
    token_info = store.tokens[token_id]
    
    print(f"[API CREATED] {endpoint} with token {token_info['symbol']} at ${token_info['price_usd']:.6f}")
    
    return jsonify({
        "success": True,
        "api": {
            "name": data["name"],
            "endpoint": endpoint,
            "token": {
                "id": token_id,
                "symbol": token_info["symbol"],
                "current_price_usd": token_info["price_usd"]
            },
            "wallet_address": data["wallet_address"],
            "test_request": f"curl -X GET http://localhost:5000{endpoint}"
        }
    }), 201


# List all APIs
@app.route("/admin/list-apis", methods=["GET"])
def list_apis():
    """List all created APIs and their current prices"""
    apis_info = []
    for endpoint, api_config in store.apis.items():
        token_id = api_config["token_id"]
        token = store.tokens[token_id]
        apis_info.append({
            "name": api_config["name"],
            "endpoint": endpoint,
            "token": {
                "symbol": token["symbol"],
                "current_price_usd": token["price_usd"]
            },
            "wallet_address": api_config["wallet_address"]
        })
    
    return jsonify({
        "total_apis": len(apis_info),
        "apis": apis_info
    })


# Health check
@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "running",
        "message": "x402 Dynamic API Server",
        "endpoints": {
            "create_api": "POST /admin/create-api",
            "list_apis": "GET /admin/list-apis"
        },
        "active_apis": len(store.apis)
    })


if __name__ == "__main__":
    # Start price update thread
    price_thread = threading.Thread(target=store.update_prices, daemon=True)
    price_thread.start()
    
    print("=" * 60)
    print("x402 Dynamic API Server Starting...")
    print("=" * 60)
    print("\nCreate an API with:")
    print("""
curl -X POST http://localhost:5000/admin/create-api \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Weather API",
    "endpoint": "/weather",
    "wallet_address": "0x1234567890abcdef",
    "description": "Get weather data",
    "handler": "weather_data"
  }'
    """)
    print("\n" + "=" * 60)
    
    app.run(debug=True, port=5000, use_reloader=False)