"""Paper trading of Nifty weekly options, priced from Breeze. Simulation only - no orders are ever placed.

config.py   - every assumption in one place (rule, contract, lot size, costs); override via data/paper/config.json
costs.py    - Indian F&O charges per fill
market.py   - the data the engine needs (Nifty daily bars, option opens/closes), from Breeze history
engine.py   - the daily cycle: fill at the open, mark at the close, decide for the next open
ledger.py   - JSON persistence (data/paper/ledger.json) and read helpers
routes.py   - /api/paper/* endpoints; runner.py - background loop that keeps the ledger current

Everything is priced from historical data, so a day missed while the backend was down or logged out is
processed correctly on the next run - the record never depends on having watched the market live.
"""
