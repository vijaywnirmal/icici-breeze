# WebSocket Subscription Guide

## Overview
This guide shows how to enable WebSocket feeds for all tokens from your instruments table using the exact pattern you requested: `breeze.subscribe_feeds(stock_token=[...])`.

## What's Been Implemented

### 1. Bulk WebSocket Service (`backend/services/bulk_websocket_service.py`)
- Fetches all active tokens from the instruments table
- Formats tokens correctly for Breeze API (4.1!TOKEN format for NSE)
- Handles batch subscriptions to avoid API limits
- Manages WebSocket connections and subscriptions

### 2. API Endpoints (`backend/routes/bulk_websocket.py`)
- `GET /api/bulk-websocket/tokens?limit=N` - Get available tokens
- `POST /api/bulk-websocket/subscribe-sample` - Subscribe to sample tokens
- `POST /api/bulk-websocket/subscribe-all` - Subscribe to all tokens
- `GET /api/bulk-websocket/status` - Get subscription status
- `POST /api/bulk-websocket/unsubscribe-all` - Unsubscribe from all

### 3. Demo Scripts
- `demo_websocket_subscription.py` - Shows the exact usage pattern
- `enable_all_websockets.py` - Direct script to enable all WebSocket feeds

## Usage Examples

### Method 1: Direct API Usage
```bash
# Get available tokens
curl "http://localhost:8000/api/bulk-websocket/tokens?limit=10"

# Subscribe to sample tokens
curl -X POST "http://localhost:8000/api/bulk-websocket/subscribe-sample?sample_size=5"

# Subscribe to all tokens
curl -X POST "http://localhost:8000/api/bulk-websocket/subscribe-all"

# Check status
curl "http://localhost:8000/api/bulk-websocket/status"
```

### Method 2: Using the Service Directly
```python
from backend.services.bulk_websocket_service import BULK_WS_SERVICE
from backend.utils.session import get_breeze

# Get all tokens from database
instruments = BULK_WS_SERVICE.get_all_tokens()
formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)

# Connect to Breeze WebSocket
breeze = get_breeze()  # Your active Breeze session
breeze.client.ws_connect()

# Subscribe to all tokens using the exact pattern you requested:
breeze.client.subscribe_feeds(stock_token=formatted_tokens)
```

### Method 3: WebSocket Client Subscription
```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/ticks');

ws.onopen = () => {
    // Subscribe to multiple tokens
    ws.send(JSON.stringify({
        "action": "subscribe_many",
        "symbols": [
            {
                "stock_code": "NIFTY",
                "token": "4.1!3499",
                "exchange_code": "NSE",
                "product_type": "cash"
            },
            {
                "stock_code": "BANKNIFTY",
                "token": "4.1!2885",
                "exchange_code": "NSE",
                "product_type": "cash"
            }
        ]
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'tick') {
        console.log(`Received tick: ${data.symbol} - LTP: ${data.ltp}`);
    }
};
```

## Token Formatting

All tokens are automatically formatted for the Breeze API:
- NSE tokens: `4.1!TOKEN` (e.g., `4.1!3499` for NIFTY)
- BSE tokens: `1.1!TOKEN` (e.g., `1.1!1234` for BSE stocks)

## Current Database Status

- **Total instruments**: 2,141
- **WebSocket enabled**: 2,141 (all active)
- **Exchange**: All tokens are treated as NSE (4.1! format)

## Sample Tokens Available

From your instruments table:
- `4.1!10` - ABAOFF (ABAN OFFSHORE LTD)
- `4.1!100` - AMARAJ (AMARA RAJA ENERGY & MOBILITY)
- `4.1!10056` - SKMEGG (SKM EGG PRODUCTS EXPORTS)
- `4.1!10065` - BININD (BIL VYAPAR LIMITED)
- `4.1!10074` - EMAPAP (EMAMI PAPER MILLS LIMITED)
- And 2,136 more...

## Running the Demo

```bash
# Show the exact usage pattern
python demo_websocket_subscription.py

# Test with sample tokens (requires Breeze session)
python enable_all_websockets.py --test

# Subscribe to all tokens (requires Breeze session)
python enable_all_websockets.py --all
```

## Requirements

1. **Active Breeze Session**: You need to be logged in to Breeze API
2. **Database**: Instruments table must be populated
3. **Server Running**: Backend server on port 8000

## Next Steps

1. **Login to Breeze**: Ensure you have an active Breeze session
2. **Test Sample**: Run `python enable_all_websockets.py --test` to test with a few tokens
3. **Enable All**: Run `python enable_all_websockets.py --all` to subscribe to all 2,141 tokens
4. **Monitor**: Use the WebSocket endpoint to receive real-time data

## WebSocket Data Format

When subscribed, you'll receive real-time data in this format:
```json
{
    "type": "tick",
    "symbol": "NIFTY",
    "ltp": 19500.50,
    "close": 19450.25,
    "bid": 19500.00,
    "ask": 19501.00,
    "change_pct": 0.26,
    "timestamp": "2025-09-05T12:30:00Z"
}
```

This implementation provides exactly what you requested: the ability to enable WebSocket feeds for all tokens using `breeze.subscribe_feeds(stock_token=[...])` with proper token formatting and batch processing.
