import uvicorn
from fastapi import FastAPI, HTTPException, Request, Header
from typing import Dict, Any, Optional

app = FastAPI()

# ---------------------------------------------------------
# 1. In-Memory Database & State
# ---------------------------------------------------------
CONTENT_REGISTRY: Dict[str, Any] = {}

# SIMULATION STATE: We store the "current market price" here.
# In production, this variable would be updated by a background task
# fetching from CoinGecko/Chainlink every 60 seconds.
MARKET_PRICE_ETH = 2000.0

# ---------------------------------------------------------
# 2. Dynamic Price Calculator
# ---------------------------------------------------------
def get_dynamic_price_in_eth(base_price_usd: float) -> str:
    # 1. Use the global "live" price
    global MARKET_PRICE_ETH
    
    # Safety check to prevent division by zero
    if MARKET_PRICE_ETH <= 0:
        return "0.000000"
        
    # 2. Calculate exact ETH amount needed
    amount_eth = base_price_usd / MARKET_PRICE_ETH
    
    # 3. Format strictly as string for x402 (e.g., "0.005000")
    return f"{amount_eth:.6f}"

# ---------------------------------------------------------
# 3. The "Oracle" Endpoint (For Testing/Simulation)
# ---------------------------------------------------------
# CHANGED TO @app.get SO YOU CAN PASTE IN BROWSER
@app.get("/oracle/set-price")
async def set_market_price(price: float):
    """
    Simulates the market moving. Call this to change the price of ETH.
    Usage: /oracle/set-price?price=1000
    """
    global MARKET_PRICE_ETH
    MARKET_PRICE_ETH = price
    return {"status": "market_updated", "current_eth_price": MARKET_PRICE_ETH}

# ---------------------------------------------------------
# 4. The "Create" Endpoint
# ---------------------------------------------------------
# CHANGED TO @app.get SO YOU CAN PASTE IN BROWSER
@app.get("/create-paywall")
async def create_paywall(paywall_id: str, content: str, price_usd: float, wallet: str):
    """
    Creates a new paywall configuration.
    Usage: /create-paywall?paywall_id=test1&content=Secret&price_usd=20&wallet=0x123
    """
    if paywall_id in CONTENT_REGISTRY:
        # For demo purposes, we'll just update it if it exists so you don't get errors retrying
        pass
    
    CONTENT_REGISTRY[paywall_id] = {
        "content": content,
        "base_price_usd": price_usd,
        "wallet_address": wallet
    }
    return {"status": "created", "url": f"/access/{paywall_id}"}

# ---------------------------------------------------------
# 5. The Dynamic "Gate" Endpoint
# ---------------------------------------------------------
@app.get("/access/{paywall_id}")
async def access_content(
    paywall_id: str, 
    request: Request,
    # x402 clients verify payment via these headers
    x_payment_token: Optional[str] = Header(None, alias="X-Payment-Token") 
):
    # A. Retrieve Configuration
    item = CONTENT_REGISTRY.get(paywall_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # B. Calculate REAL-TIME Price
    # This runs NOW, using whatever MARKET_PRICE_ETH is currently set to.
    current_price_eth = get_dynamic_price_in_eth(item["base_price_usd"])
    
    # C. CHECK PAYMENT (The x402 Logic)
    if not x_payment_token:
        raise HTTPException(
            status_code=402,
            detail="Payment Required",
            headers={
                # x402 Standard Headers
                "x402-price": current_price_eth,
                "x402-currency": "ETH",
                "x402-network": "base-sepolia",
                "x402-recipient": item["wallet_address"],
                # Standard HTTP 402 Headers
                "WWW-Authenticate": f'Token realm="x402", price="{current_price_eth}", currency="ETH"'
            }
        )

    # D. VERIFY PAYMENT (Future Step)
    # verify_x402_token(x_payment_token, expected_amount=current_price_eth)
    
    # E. Return Content
    return {
        "content": item["content"],
        "status": "unlocked", 
        "paid_amount": current_price_eth,
        "market_price_used": MARKET_PRICE_ETH
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)