"""Intraday paper trading of Nifty weekly options, priced from Breeze. Simulation only - no orders are placed.

config.py   - every assumption in one place (signal, contract, exits, costs); override via data/paper/config.json
costs.py    - Indian F&O charges per fill
market.py   - the data the engine needs (Nifty daily + 5-minute bars, option 1-minute bars), from Breeze history
engine.py   - one session at a time: RSI signal -> ATM option -> target / stop / square-off, plus replay data
ledger.py   - JSON persistence (data/paper/) and read helpers
routes.py   - /api/paper/* endpoints; runner.py - background loop that keeps the record current
backtest.py - the same engine over a range of past sessions: report, in/out-of-sample split, parameter sweeps

Everything is priced from historical data, so a session can be simulated after the close, and days missed
while the backend was down or logged out are processed on the next run.
"""
