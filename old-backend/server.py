# write a server.py that can 
# given a transcript: 

# a) calls a function  that sees if any of the statemnets could match anything from polymarket using a LLM (provide examples to the LLM on how unhinged it should match shit, like |
#  x) "It's so hot outside" → Bet YES on "2024 will be the hottest year on record."
#  y) "This debate is boring" → Bet NO on "Trump/Harris viewership numbers."
#  z) "I'm never getting a girlfriend" → Bet YES on "Birth rates drop in 2025.") 

# b) if it does, call a new fucntion create the transcation on polymarket (or multiple positons), then send a text message to a group chat of the positon being created using imessage macros on mac

# c) it should also call a function that checks if anything should be created as a friend market as a joke. do things like "lets drive home" --> creates an over under on time till home or like "u talking to a girl" --> will shrey get a girlfriend in 2025 etc. once created, shoudl text the link or smart contract or smth to the group chat as well

import os
import subprocess
import json
from typing import List, Dict, Any
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# -------------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------------

def send_imessage(text: str):
    """
    Uses an AppleScript macro to send an iMessage to groupchat.
    Requires macOS host running this backend.
    """
    # Escape double quotes in the text to prevent breaking the AppleScript string
    safe_text = text.replace('"', '\\"')
    
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "+1234567890" of targetService
        send "{safe_text}" to targetBuddy
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error sending iMessage: {e}")


def fetch_polymarket_markets() -> List[Dict[str, Any]]:
    """Fetches all polymarket markets."""
    url = "https://gamma-api.polymarket.com/markets?limit=1000"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # FIX: The API returns a list directly, not {"data": [...]}
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "data" in data:
            return data["data"]
        else:
            print("Unexpected API response format")
            return []
            
    except Exception as e:
        print(f"Error fetching Polymarket data: {e}")
        return []


# -------------------------------------------------------------------------
# A) LLM MATCHER (Unhinged semantic linking)
# -------------------------------------------------------------------------

def match_statements_to_polymarket(transcript: str, markets: List[Dict[str, Any]]):
    """
    Returns a list of matched markets with suggested YES/NO positions.
    Uses an intentionally-unhinged LLM to find any remote connection.
    """
    
    # Safety check if markets failed to load
    if not markets:
        return {"matches": []}

    # Format market titles for context
    # Use .get() to avoid KeyErrors if some market objects are malformed
    market_titles = [m.get("question", "Unknown Market") for m in markets[:200]] # Limit context to 200 to save tokens
    joined_titles = "\n".join(f"- {t}" for t in market_titles)

    prompt = f"""
You are an UNHINGED semantic matcher. 
Your job: connect what a human says to SOMEWHAT relevant prediction market.
Stretch the meaning quite a lot. Examples:

x) "It's so hot outside" → Bet YES on "2024 will be the hottest year on record."
y) "This debate is boring" → Bet NO on "Trump/Harris viewership numbers."
z) "I'm never getting a girlfriend" → Bet YES on "Birth rates drop in 2025."
a) "I feel tired" → Bet YES on "US recessions probability."
b) "Traffic sucks today" → Bet YES on "Gas price increase by end of month."

DO NOT make NON OBVIOUS, RANDOM connections. DO MAKE OUTLANDISH connections.
OUTLANDISH example (VERY GOOD): "I'm never getting a girlfriend" → Bet YES on "Birth rates drop in 2025." (Birth rates arent actually gonna move if you get a girlfriend its negligable) 
NON OBVIOUS, RANDOM connection (VERY BAD): "I'm never getting a girlfriend" → bet YES on lebron devorcing his wife (THIS IS BAD, this IS NON OBVIOUS and RANDOM)

Given the transcript:
“{transcript}”

And these Polymarket markets:
{joined_titles}

Output STRICT JSON in this format:
{{
  "matches": [
    {{
      "market_title": "...",
      "reasoning": "...",
      "recommended_position": "YES or NO"
    }}
  ]
}}

"""

    print(f"🎤 Transcript received: {transcript}")
    print(f"🎤 Markets received: {markets}")
    print(f"🎤 Prompt: {prompt}")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "MBC Backend",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "openai/gpt-4-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"} # Force JSON mode
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return json.loads(text)
    except Exception as e:
        print(f"Error calling OpenRouter (Polymarket Match): {str(e)}")
        return {"matches": []}

# -------------------------------------------------------------------------
# B) EXECUTE POLYMARKET TRADE (stub for hackathon)
# -------------------------------------------------------------------------

def execute_polymarket_trade(market_title: str, side: str):
    """
    Stub: In a real version you'd call Polymarket's trading API or contract.
    For hackathon demo, we pretend we did and return a fake receipt.
    """
    # TODO: integrate real Polymarket trading logic
    print(f"[MOCK TRADE] Executing {side} on '{market_title}'")
    return {
        "market_title": market_title,
        "side": side,
        "tx_hash": "0xFAKE_TRANSACTION_HASH"
    }


# -------------------------------------------------------------------------
# C) FRIEND MARKET CREATION (fun lightweight classifier)
# -------------------------------------------------------------------------

def detect_friend_market(transcript: str):
    """
    Uses LLM to detect funny/chaotic "friend markets" to create.
    """

    prompt = f"""
You generate FUNNY CHAOTIC 'friend markets' based on what someone says.

Examples:
- "let's drive home" → "Over/Under: 12.5 minutes until arrival"
- "you talking to a girl?" → "Will Shrey get a girlfriend in 2025?"
- "I'm hungry" → "Will we stop for food in the next 20 minutes?"
- "I'm tired" → "Will he fall asleep before midnight?"

Given transcript: "{transcript}"

If NO friend market should be created, return:
{{"should_create": false}}

If one SHOULD be created, return:
{{
  "should_create": true,
  "market_title": "...",
  "market_type": "YESNO or OVERUNDER",
  "initial_odds": "..."
}}


IMPORTANT: You MUST output valid JSON.
Format:
{{
  "should_create": true,
  "market_title": "...",
  "market_type": "YESNO or OVERUNDER",
  "initial_odds": "0.5"
}}

"""

    print(f"🎤 Prompt: {prompt}")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "MBC Backend",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "openai/gpt-4-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return json.loads(text)
    except Exception as e:
        print(f"Error calling OpenRouter: {str(e)}")
        return {"should_create": False}


def create_friend_market_onchain(title: str):
    """
    Stub: Creates a YES/NO market on Base or Solana using USDC.
    """
    # TODO: Deploy minimal contract or reuse factory
    print(f"[MOCK FRIEND MARKET] Creating onchain market: {title}")
    return {
        "market_title": title,
        "contract_address": "0xFAKE_FRIEND_MARKET"
    }


# -------------------------------------------------------------------------
# MAIN ENDPOINT
# -------------------------------------------------------------------------

@app.route("/process_transcript", methods=["POST"])
def process_transcript():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON payload provided"}), 400
        
    transcript = data.get("transcript", "")
    print(f"🎤 Transcript received: {transcript}")

    # 1) Get Polymarket markets
    markets = fetch_polymarket_markets()
    print(f"✅ Fetched {len(markets)} markets from Polymarket")

    # 2A) TRY MATCHING TO POLYMARKET
    match_result = match_statements_to_polymarket(transcript, markets)
    
    created_positions = []
    if match_result and "matches" in match_result:
        for m in match_result["matches"]:
            receipt = execute_polymarket_trade(
                m["market_title"],
                m["recommended_position"]
            )
            created_positions.append(receipt)

            # Notify groupchat
            send_imessage(
                f"🔮 Auto-bet created!\n"
                f"Market: {m['market_title']}\n"
                f"Side: {m['recommended_position']}\n"
                f"Reason: {m['reasoning']}"
            )

    # 2C) FRIEND MARKET CHECK
    fm = detect_friend_market(transcript)
    friend_market = None
    if fm and fm.get("should_create"):
        friend_market = create_friend_market_onchain(fm["market_title"])

        send_imessage(
            f"🤣 NEW FRIEND MARKET CREATED!\n"
            f"{fm['market_title']}\n"
            f"Contract: {friend_market['contract_address']}"
        )

    return jsonify({
        "polymarket_positions": created_positions,
        "friend_market": friend_market
    })


# -------------------------------------------------------------------------
# RUN
# -------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(port=5001, debug=True)