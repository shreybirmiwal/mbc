import os
import requests
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
# Ensure you set this environment variable before running:
# export OPENROUTER_API_KEY="sk-or-..."
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Use Vercel URL in production, localhost in development
YOUR_SITE_URL = os.getenv("VERCEL_URL", "http://localhost:5000")
if YOUR_SITE_URL and not YOUR_SITE_URL.startswith("http"):
    YOUR_SITE_URL = f"https://{YOUR_SITE_URL}"
YOUR_SITE_NAME = os.getenv("SITE_NAME", "Demo APIs Server")   # Optional, for OpenRouter rankings

def call_openrouter(model_name, user_prompt):
    """
    Helper function to send requests to OpenRouter.
    """
    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY not set in environment variables."}

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_SITE_NAME,
        "Content-Type": "application/json"
    }

    data = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": user_prompt}
        ]
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data)
        response.raise_for_status() # Raise error for bad status codes
        
        # Parse the OpenRouter response
        result_json = response.json()
        
        # Extract just the content text
        content = result_json['choices'][0]['message']['content']
        
        return {"output": content}

    except requests.exceptions.RequestException as e:
        return {"output": f"Error calling API: {str(e)}"}
    except (KeyError, IndexError):
        return {"output": "Error parsing response from provider."}

# ------------------------------------------------------------------
# AI ROUTES (Strict Output Preserved)
# ------------------------------------------------------------------

@app.route('/mistral', methods=['POST'])
def route_mistral():
    """Route specifically for Mistral 7B"""
    data = request.json
    prompt = data.get('prompt', '')
    response = call_openrouter("mistralai/mistral-7b-instruct:free", prompt)
    return jsonify(response)

@app.route('/llama3', methods=['POST'])
def route_llama():
    """Route specifically for Llama 3"""
    data = request.json
    prompt = data.get('prompt', '')
    response = call_openrouter("meta-llama/llama-3-8b-instruct:free", prompt)
    return jsonify(response)

@app.route('/gemini', methods=['POST'])
def route_gemini():
    """Route specifically for Google Gemini"""
    data = request.json
    prompt = data.get('prompt', '')
    response = call_openrouter("google/gemini-pro", prompt)
    return jsonify(response)

@app.route('/generic', methods=['POST'])
def route_generic():
    """Generic route where you can specify the model in the JSON body."""
    data = request.json
    prompt = data.get('prompt', '')
    model = data.get('model', 'mistralai/mistral-7b-instruct:free')
    response = call_openrouter(model, prompt)
    return jsonify(response)

# ------------------------------------------------------------------
# UTILITY & FUN API ROUTES (Raw JSON Data)
# ------------------------------------------------------------------

@app.route('/weather', methods=['GET', 'POST'])
def route_weather():
    """
    Get weather using Open-Meteo.
    Returns full JSON object from the provider.
    """
    # Try to get lat/long from JSON body (POST) or Query Params (GET)
    lat = 52.52
    lon = 13.41
    
    if request.method == 'POST' and request.json:
        lat = request.json.get('lat', lat)
        lon = request.json.get('lon', lon)
    elif request.args.get('lat'):
        lat = request.args.get('lat')
        lon = request.args.get('lon')
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m"
    
    try:
        resp = requests.get(url)
        # Return the raw JSON data so the frontend can use temperature, wind, etc.
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": f"Error fetching weather: {str(e)}"})

@app.route('/bitcoin', methods=['GET'])
def route_bitcoin():
    """Get current Bitcoin Price via Coindesk (Raw JSON)"""
    url = "https://api.coindesk.com/v1/bpi/currentprice.json"
    try:
        resp = requests.get(url)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": "Failed to fetch Bitcoin price."})

@app.route('/fact', methods=['GET'])
def route_fact():
    """Get a random useless fact (Raw JSON)"""
    url = "https://uselessfacts.jsph.pl/api/v2/facts/random"
    try:
        resp = requests.get(url)
        return jsonify(resp.json())
    except Exception:
        return jsonify({"error": "Did you know? I couldn't fetch a fact right now."})

@app.route('/joke', methods=['GET'])
def route_joke():
    """Get a random joke (Raw JSON)"""
    url = "https://official-joke-api.appspot.com/random_joke"
    try:
        resp = requests.get(url)
        # Returns {type, setup, punchline, id}
        return jsonify(resp.json())
    except Exception:
        return jsonify({"error": "Failed to fetch joke"})

@app.route('/time', methods=['GET'])
def route_time():
    """Get server current time in structured format"""
    now = datetime.datetime.now()
    return jsonify({
        "iso": now.isoformat(),
        "timestamp": now.timestamp(),
        "readable": now.strftime('%Y-%m-%d %H:%M:%S'),
        "year": now.year,
        "month": now.month,
        "day": now.day
    })

if __name__ == '__main__':
    print("Starting server on port 5000...")
    app.run(debug=True, port=5000)