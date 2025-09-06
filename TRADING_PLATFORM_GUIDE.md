# 📈 Live Trading Platform Guide

Your ICICI Breeze Trading Platform now includes a comprehensive live trading interface similar to popular platforms like Groww, Kite, and Upstox!

## 🚀 Quick Start

### 1. Start the Backend Server
```bash
cd backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Frontend
```bash
cd frontend
npm run dev
```

### 3. Access the Trading Platform
Navigate to: **http://localhost:5173/live-trading**

## 🎯 Features

### 🔍 **Stock Search**
- **Real-time search** as you type (300ms debounce)
- Search by **company name** or **symbol**
- **Instant results** from your instruments database
- Only shows **WebSocket-enabled** stocks for live data

### 📋 **Watchlist Management**
- **Add stocks** to your personal watchlist
- **Persistent storage** in browser localStorage
- **Remove stocks** with one click
- **Drag & drop** support (coming soon)

### 📊 **Live Price Display**
- **Real-time LTP** (Last Traded Price)
- **Live change percentage** with color coding
- **Bid/Ask prices** when available
- **Market status indicator** (Open/Closed)

### 🎨 **Modern UI/UX**
- **Dark theme** with professional styling
- **Responsive design** for all screen sizes
- **Smooth animations** and hover effects
- **Tabbed interface** for easy navigation

## 📱 How to Use

### Step 1: Search for Stocks
1. Go to the **Search** tab
2. Type a company name or symbol (e.g., "RELIANCE", "TCS", "HDFC")
3. Browse the search results
4. Click **"+ Add to Watchlist"** on any stock

### Step 2: Monitor Live Prices
1. Switch to the **Watchlist** tab
2. View all your selected stocks
3. See **live prices** when market is open
4. **Green** = positive change, **Red** = negative change

### Step 3: Manage Your Watchlist
- **Remove stocks** by clicking the "×" button
- **Reorder stocks** by dragging (coming soon)
- **Add more stocks** by searching again

## 🔧 Technical Details

### API Endpoints Used
- `GET /api/instruments/live-trading` - Search stocks
- `GET /api/market/status` - Check market status
- `WebSocket /ws/ticks` - Live price data

### WebSocket Message Format
```json
{
  "action": "subscribe",
  "symbol": "RELIANCE",
  "exchange_code": "NSE",
  "product_type": "cash"
}
```

### Live Data Format
```json
{
  "type": "tick",
  "symbol": "RELIANCE",
  "ltp": 2456.50,
  "change_pct": 1.25,
  "bid": 2456.00,
  "ask": 2457.00,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🎨 UI Components

### Stock Card
Each stock is displayed in a beautiful card showing:
- **Symbol** (e.g., RELIANCE)
- **Company Name** (e.g., Reliance Industries Ltd)
- **Exchange** (NSE)
- **Live LTP** (Last Traded Price)
- **Change %** (with color coding)
- **Bid/Ask** (when available)

### Search Results
- **Grid layout** for easy browsing
- **Hover effects** for better UX
- **Add button** for quick watchlist addition
- **Loading indicator** during search

### Market Status
- **🟢 Market Open** - Live data available
- **🔴 Market Closed** - Live data unavailable
- **Real-time updates** based on market hours

## 🔐 Login Required

The platform requires you to login first through the main interface:
- **API Key** and **API Secret** for authentication
- **Session Token** for maintaining connection
- **Manual login** required before using trading features

## 🚀 Future Enhancements

### Planned Features
- **📊 Trending Stocks** tab with volume-based rankings
- **📈 Price Charts** integration
- **🔔 Price Alerts** and notifications
- **📱 Mobile-optimized** interface
- **🎯 Advanced Filters** (sector, market cap, etc.)
- **💾 Portfolio Tracking** and P&L calculation

### Advanced Features
- **Real-time order placement** (when trading APIs are integrated)
- **Market depth** display
- **News integration** for each stock
- **Technical indicators** overlay
- **Custom watchlists** with categories

## 🐛 Troubleshooting

### Common Issues

#### 1. No Search Results
- **Check**: Database connection
- **Verify**: WebSocket-enabled stocks exist
- **Solution**: Run `python test_trading_platform.py`

#### 2. No Live Prices
- **Check**: Market is open
- **Verify**: WebSocket connection
- **Solution**: Check browser console for errors

#### 3. No Live Data
- **Check**: You are logged in
- **Verify**: Market is open
- **Solution**: Login through the main interface first

### Debug Commands
```bash
# Test the trading platform
python test_trading_platform.py

# Verify database
python check_instruments.py
```

## 📞 Support

If you encounter any issues:
1. Check the **browser console** for errors
2. Verify the **backend server** is running
3. Test the **API endpoints** manually
4. Check the **WebSocket connection** status

## 🎉 Success!

You now have a fully functional trading platform that rivals commercial solutions! The platform provides:

✅ **Real-time stock search**  
✅ **Live price monitoring**  
✅ **Personal watchlist**  
✅ **Professional UI/UX**  
✅ **Manual login integration**  
✅ **WebSocket streaming**  

**Happy Trading! 📈🚀**
