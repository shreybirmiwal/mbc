## chaining apis x402 with dyanic pricing, buy/sell/trading
API for rverything Human in loop asw
Ratings
Agent kit usage
Dynamic prices for each api (each api u Have to buy it and exchange it in some token or smth, so it has dynamic prices chart and shi)
Coming soon for adding new tokens
Main feature
- can see all apis
- can build and chain them
Can get specific variables when chaining
Should we make token direct buy item? Or shd it be seperate token and then usdc buy
Demo dummy for certain plug in apis
Robotic, science, human, ai
APIs etc




1. you can create your api and start getting paid
--> upload ur api link and the parameters it takes
--> it creates a x402 api on our server
--> it creates a new token on base
--> the pricing of ur api is dynamic based on the token

2. people can see all apis on the market place
drag and drop interface to chain apis together, take parameters from one and outputs from one and put into inputs of next

3. total quoted price created

cool ux

steps to create
1. SERVER THAT PRICE / ROUTE UPDATES DYNAMIC
create a server that we can 
 -- add new routes that are 402 on run time
 -- have dynamic pricing for these 402 

2. frontend with one button that
-- creates token on base
-- creates new api on our server
-- links api to token
another button to
-- buy that api and get result



you can chain together any apis on our site







# 1.
how would you create a python server that
when a specific route is called, ie, 'activate-new-route'

the server it self:
 -- adds a new route to it self

I am trying to make a minimvially viable working demo for this, then extend it, so keep it DEAD SIMPLE and working.

the next future steps (dont do yet, but keep in mind)

-- this new route is a x402 activated route
here is documentation on x402:
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from x402.fastapi.middleware import require_payment
from x402.types import EIP712Domain, TokenAmount, TokenAsset

# Load environment variables
load_dotenv()

app = FastAPI()

# Apply payment middleware to specific routes
app.middleware("http")(
    require_payment(
        path="/weather",
        price="$0.001",
        pay_to_address="0xAddress",
        network="base-sepolia",
    )
)

@app.get("/weather")
async def get_weather() -> Dict[str, Any]:
    return {
        "report": {
            "weather": "sunny",
            "temperature": 70,
        }
    }

interface PaymentMiddlewareConfig {
  description?: string;               // Description of the payment
  mimeType?: string;                  // MIME type of the resource
  maxTimeoutSeconds?: number;         // Maximum time for payment (default: 60)
  outputSchema?: Record; // JSON schema for the response
  customPaywallHtml?: string;         // Custom HTML for the paywall
  resource?: string;                  // Resource URL (defaults to request URL)
}


 -- have dynamic pricing that changes based on price of ETH (later it will change to a BASE l2 token)


https://claude.ai/share/035cfe7d-2be6-4d44-8395-5bf22e17f0e4