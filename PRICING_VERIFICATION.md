# Pricing System Verification

## Data Flow Summary

### 1. Flaunch API → Backend
The backend fetches **only 3 fields** from Flaunch API:

```python
# From: GET https://dev-api.flayerlabs.xyz/v1/{network}/tokens/{token_address}/price

response = {
    "price": {
        "priceUSDC": "0.003526509141079321505771"  # ← Used directly
    },
    "volume": {
        "volumeUSDC24h": "2598.059511",           # ← Used directly
        "volumeUSDC7d": "9088.276105"             # ← Used directly
    }
}
```

### 2. Backend Processing
```python
def get_token_price_data(token_address):
    # Extract ONLY these 3 fields:
    token_price_usd = float(price_obj.get("priceUSDC", 0))
    volume_24h_usd = float(volume_obj.get("volumeUSDC24h", 0))
    volume_7d_usd = float(volume_obj.get("volumeUSDC7d", 0))
    
    return {
        "token_price_usd": token_price_usd,
        "volume_24h_usd": volume_24h_usd,
        "volume_7d_usd": volume_7d_usd
    }
```

### 3. API Response Structure
All endpoints return pricing in this format:

```json
{
    "pricing": {
        "token_price_usd": 0.00352651,    // priceUSDC from Flaunch
        "api_price_usd": 35.2651,         // token_price × multiplier
        "price_multiplier": 10000,
        "volume_24h_usd": 2598.06,        // volumeUSDC24h from Flaunch
        "volume_7d_usd": 9088.28          // volumeUSDC7d from Flaunch
    }
}
```

### 4. Frontend Display
The frontend shows:
- **API Price per Call**: `$35.27` (transformed price)
- **Token Price**: `$0.00352651` (raw from Flaunch)
- **24h Volume**: `$2.60K`
- **7d Volume**: `$9.09K`

## What Was Removed
❌ Market cap tracking
❌ Price change 24h / percentage
❌ All-time high/low
❌ ETH conversions
❌ Price history data
❌ Complex fallback logic

## Data Verification Checklist
✅ `priceUSDC` is extracted correctly from `data.price.priceUSDC`
✅ `volumeUSDC24h` is extracted from `data.volume.volumeUSDC24h`
✅ `volumeUSDC7d` is extracted from `data.volume.volumeUSDC7d`
✅ No ETH conversions are performed
✅ Data flows cleanly: Flaunch API → Backend → Frontend
✅ Frontend displays all 3 values correctly

## Endpoints Returning Pricing Data
1. `GET /admin/list-apis` - Returns pricing for all APIs
2. `GET /admin/api-status/<endpoint>` - Returns pricing for specific API
3. `GET /admin/api-info/<endpoint>` - Returns detailed pricing + volumes
4. `POST /admin/create-api` - Returns pricing after token deployment

## Test Commands
```bash
# Start backend
cd new-backend
python claiming.py

# In another terminal, test API
curl http://localhost:5000/admin/list-apis | jq '.apis[0].pricing'

# Expected output:
# {
#   "token_price_usd": 0.00352651,
#   "api_price_usd": 35.2651,
#   "price_multiplier": 10000,
#   "volume_24h_usd": 2598.06,
#   "volume_7d_usd": 9088.28
# }
```

## Frontend Verification
1. Start frontend: `cd frontend && npm start`
2. Open http://localhost:3000
3. Check each API card shows:
   - API Price per Call (large, highlighted)
   - Token price (in transform text)
   - 24h Volume
   - 7d Volume
   - Contract address

✅ **All data flows cleanly with no conversions or unnecessary fields**

