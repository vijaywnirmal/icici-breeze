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
│   ├── requirements.in     # Top-level Python dependencies (unpinned)
│   ├── requirements.txt    # Locked Python dependencies (generated)
│   └── requirements.lock.txt # Snapshot of current environment (optional)
├── frontend/               # React frontend application
│   ├── src/               # React source code
│   ├── package.json       # Node.js dependencies
│   └── package-lock.json  # Locked Node.js dependencies (generated)
├── SecurityMaster/        # ICICI security master data
├── logs/                  # Application logs
├── run_backend.py         # Backend startup script
├── update_instruments.py  # Instruments update script
└── env.example           # Authoritative environment variables template
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

1. **Install Node.js dependencies (locked):**
   ```bash
   cd frontend
   npm ci
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

## Environment Variables

Copy `env.example` to `.env` and configure. These variables are loaded by the backend (via `dotenv`) and the frontend (Vite `VITE_*`). Do not commit real secrets.

```env
# Backend
APP_NAME="Automated Trading Platform"
ENVIRONMENT=development
BREEZE_API_KEY=
BREEZE_API_SECRET=
BREEZE_SESSION_TOKEN=
POSTGRES_DSN=
INSTRUMENTS_FIRST_RUN_ON_LOGIN=true

# Frontend
VITE_API_BASE_URL=
VITE_API_BASE_WS=
```

## Dependency Locking

### Python (Backend) with pip-tools

- Top-level requirements are in `backend/requirements.in`.
- Generate a locked `backend/requirements.txt` with hashes:
  ```bash
  pip install pip-tools
  python -m piptools compile backend/requirements.in --resolver=backtracking --generate-hashes --output-file backend/requirements.txt
  ```
- Install using the locked file:
  ```bash
  pip install --require-hashes -r backend/requirements.txt
  ```
- For a full snapshot of the current environment (optional), `backend/requirements.lock.txt` is generated via:
  ```bash
  cd backend && pip freeze > requirements.lock.txt
  ```

### Node.js (Frontend)

- Lockfile is `frontend/package-lock.json` (managed by npm).
- Clean, reproducible install:
  ```bash
  cd frontend
  npm ci
  ```

## Secret Management Policy

- Never commit plaintext credentials. Files like `.breeze_session.json`, `breeze_credentials.txt`, `cookies.txt`, and `session_data.json` are ignored by `.gitignore` and must not be used for storing secrets.
- Use a local `.env` for development and a secret manager for production (e.g., AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, 1Password).
- All code reads credentials from environment variables only. Session persistence remains in memory; no secret material is written to disk.

## Development

- Backend runs on `http://localhost:8000`
- Frontend runs on `http://localhost:5173`
- API documentation available at `http://localhost:8000/docs`
