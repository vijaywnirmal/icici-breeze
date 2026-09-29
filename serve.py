#!/usr/bin/env python3
"""Run the backend in the background (Windows logon task): localhost only, output to logs/backend.log.

    .venv\\Scripts\\pythonw.exe serve.py

Registered by nifty-reels/schedule.ps1 as "19 Breeze Backend" so the paper trader is up whenever you are
logged in. Listens on 127.0.0.1 only - a logged-in broker session shouldn't be reachable from the network
(run_backend.py binds 0.0.0.0 and auto-reloads, which suits development, not this).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    log = open(ROOT / "logs" / "backend.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log  # pythonw has no console; uvicorn and the app log here instead
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, app_dir=str(ROOT), log_level="info",
                access_log=False)


if __name__ == "__main__":
    main()
