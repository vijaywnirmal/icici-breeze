# ICICI Breeze Trading App

A comprehensive trading application built with FastAPI backend and React frontend for ICICI Breeze trading platform.

## Project Structure

```
icici-breeze-trading/
├── backend/                 # FastAPI backend application
│   ├── app.py              # Main FastAPI application
│   ├── routes/             # API route handlers
│   ├── services/           # Business logic services
│   ├── utils/              # Utility functions and helpers
│   ├── templates/          # Strategy templates
│   ├── requirements.txt    # Python dependencies
│   └── create_instruments_table.py  # Instruments table management
├── frontend/               # React frontend application
│   ├── src/               # React source code
│   ├── package.json       # Node.js dependencies
│   └── vite.config.js     # Vite configuration
├── SecurityMaster/        # ICICI security master data
├── logs/                  # Application logs
├── run_backend.py         # Backend startup script
├── update_instruments.py  # Instruments update script
└── env.example           # Environment variables template
```

## Quick Start

### Backend Setup

1. **Install Python dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   ```bash
   cp env.example .env
   # Edit .env with your ICICI Breeze credentials
   ```

3. **Run the backend:**
   ```bash
   # From project root
   python run_backend.py
   ```

### Frontend Setup

1. **Install Node.js dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Run the frontend:**
   ```bash
   npm run dev
   ```

### Update Instruments Table

To update the instruments table with latest NSE data:

```bash
# From project root
python update_instruments.py
```

## Features

- **Live Trading**: Real-time stock price monitoring with WebSocket
- **Backtesting**: Strategy backtesting with historical data
- **Nifty 50**: Nifty 50 stock tracking and analysis
- **Strategy Builder**: Custom trading strategy creation
- **Holiday Calendar**: Market holiday tracking

## API Endpoints

- `GET /api/login` - User authentication
- `GET /api/instruments/search` - Search instruments
- `GET /api/instruments/live-trading` - Live trading instruments
- `GET /api/nifty50/stocks` - Nifty 50 stocks
- `GET /api/historical/daily` - Historical data
- `WS /ws/ticks` - WebSocket for live prices

## Environment Variables

Copy `env.example` to `.env` and configure:

```env
ICICI_API_KEY=your_api_key
ICICI_API_SECRET=your_api_secret
ICICI_SESSION_KEY=your_session_key
DATABASE_URL=your_database_url
```

## Development

- Backend runs on `http://localhost:8000`
- Frontend runs on `http://localhost:5173`
- API documentation available at `http://localhost:8000/docs`
