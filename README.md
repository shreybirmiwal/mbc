# Bazaar




## Demo Video
https://www.youtube.com/watch?v=8rU6OIX4LAM

---

## Table of Contents
1. [Description](#description)
2. [Technical Summary](#technical-summary)
3. [Setup](#setup)
4. [Local Run Steps](#local-run-steps)
5. [Architecture Overview](#architecture-overview)
6. [Deployed Contracts](#deployed-contracts)

---

## Description

Bazaar tokenizes API pricing structures, creating a dynamic marketplace where each API has its own tradeable token. Similar to how BaseApp and Zora tokenize creator coins, Bazaar tokenizes API access.

Each API is priced per usage according to the market value of its token. For example, using Gemini 3.0 may require spending a $GEM3 token, while Claude usage uses a $CLAUDE token. As token prices fluctuate based on demand, API costs automatically adjust—higher demand increases the cost, while lower demand decreases it.

By tokenizing API pricing, markets become flexible and efficient. Developers can buy tokens, trade with other APIs, sell excess API credits, and take speculative positions on API tokens. Self-correcting prices regulated by supply and demand optimize production and consumption, minimizing deadweight loss and maximizing social marginal utility.

Bazaar integrates with x402 for dynamic payments and Flaunch for token launches and bonding curve mechanics. A Flask backend manages API metadata and interfaces with a React frontend for trading and calling APIs.

---

## Technical Summary

### Problem Being Solved

API pricing is static and disconnected from actual demand/supply because rates are sticky. Providers must guess rates, leading to inefficiencies, wasted resources, or overcharging users. Bazaar addresses this by creating market-driven pricing that adjusts dynamically based on real demand.

### Layer 2 Advantages (Base)

Bazaar is deployed on Base because we can get low fees, fast transaction settlement, and built-in support for x402.

- We use x402 to handle the automatic API payment system.
- We use Flaunch API to create bonding curve price updates to handle the pricing, order matching, etc.
- We use dexScreener to serve the pricing data for each API.

### EVM Stack Usage

- API tokens are launched via Flaunch, which handles bonding-curve pricing, liquidity, and trading.
- Payments and API usage enforcement are handled through x402.

### Off-Chain Components

The Flask backend manages API metadata, triggers Flaunch token launches, and wraps APIs via x402. The React frontend provides a user-friendly interface for uploading APIs, viewing tokens, trading, and calling APIs. All heavy logic for pricing, token mechanics, and payment settlement is delegated to Flaunch and x402.

---

## Setup

### Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn
- A Base network wallet (for testing with x402 payments)

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install Flask==3.0.0 requests==2.31.0 python-dotenv x402
```

4. Create a `.env` file (if needed for custom configuration):
```bash
# .env file (optional)
# Add any environment variables here
```

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

---

## Local Run Steps

### 1. Start the Backend Server

From the `backend` directory:

```bash
python server.py
```

The backend server will start on `http://localhost:5000`.

You should see output indicating:
- x402 + Flaunch API Server
- Protocol: x402
- Network: base
- Chain ID: 8453 (Base mainnet)
- Facilitator: Mogami Facilitator (mainnet)

### 2. Start the Frontend Development Server

In a new terminal, from the `frontend` directory:

```bash
npm start
```

The frontend will start on `http://localhost:3000` and automatically open in your browser.

The frontend is configured to proxy API requests to the backend at `http://localhost:5000`.

### 3. Using the Application

1. **Create an API**: Use the frontend interface to upload an API endpoint. This will:
   - Launch a token on Flaunch
   - Register the API with x402 payment middleware
   - Create a dynamic pricing route

2. **View APIs**: Browse all available APIs in the marketplace

3. **Build Workflows**: Use the drag-and-drop workflow builder to chain multiple APIs together

4. **Call APIs**: Make API calls that require x402 payments in USDC on Base network

### Testing API Endpoints

You can test the backend directly using curl:

```bash
# Health check
curl http://localhost:5000/

# List all APIs
curl http://localhost:5000/admin/list-apis

# Create a new API
curl -X POST http://localhost:5000/admin/create-api \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example API",
    "endpoint": "/example",
    "target_url": "https://api.example.com/data",
    "method": "GET",
    "wallet_address": "0xYourWalletAddress",
    "description": "An example API"
  }'
```

---

## Architecture Overview

### System Components

```
┌─────────────────┐
│  React Frontend │
│  (Port 3000)    │
└────────┬────────┘
         │ HTTP Proxy
         ▼
┌─────────────────┐
│  Flask Backend  │
│  (Port 5000)    │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    │         │              │             │
    ▼         ▼              ▼             ▼
┌────────┐ ┌──────┐    ┌──────────┐  ┌──────────┐
│  x402  │ │Flaunch│    │Flaunch   │  │  Target  │
│Payment │ │Launch│    │Data API  │  │   APIs   │
│Protocol│ │ API  │    │(Pricing) │  │          │
└────────┘ └──────┘    └──────────┘  └──────────┘
```

### Data Flow

1. **API Creation Flow**:
   - User submits API details via frontend
   - Backend calls Flaunch API to launch a new ERC-20 token
   - Token address is stored and linked to the API endpoint
   - x402 middleware is configured with initial pricing
   - Price sync thread begins polling Flaunch for price updates

2. **API Call Flow**:
   - User makes request to API endpoint
   - x402 middleware intercepts and verifies payment
   - Payment is processed via USDC on Base network
   - Request is proxied to target API
   - Response is returned to user

3. **Price Update Flow**:
   - Background thread polls Flaunch Data API every 30 seconds
   - Token prices are fetched and transformed (multiplied) to API prices
   - x402 middleware routes are updated with new prices
   - Frontend displays real-time price updates

### Key Technologies

- **Frontend**: React 19, React Scripts
- **Backend**: Flask 3.0, Python
- **Blockchain**: Base Network (Ethereum L2)
- **Payment Protocol**: x402 (automatic API payments)
- **Token Launch**: Flaunch (bonding curve DEX)
- **Price Data**: Flaunch Data API, dexScreener

### File Structure

```
mbc/
├── backend/
│   ├── server.py              # Main Flask server with x402 integration
│   └── preexisting_routes.json # Persisted API configurations
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main React application
│   │   ├── WorkflowBuilder.js # Drag-and-drop workflow builder
│   │   └── ...
│   └── package.json
└── README.md
```

---

## Additional Resources

- [x402 Documentation](https://x402.dev)
- [Flaunch Platform](https://flaunch.gg)
- [Base Network](https://base.org)
- [Demo Video](https://www.youtube.com/watch?v=8rU6OIX4LAM)
