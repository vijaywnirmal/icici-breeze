#!/usr/bin/env python3
"""Hand today's Breeze session to the running backend, then bring the paper record up to date.

    .venv\\Scripts\\python daily_login.py            # opens ICICI's login page, then asks for the session token
    .venv\\Scripts\\python daily_login.py TOKEN      # if you already have today's token

Breeze sessions last a day. After you log in on ICICI's page it redirects to your app's redirect URL with
`?apisession=XXXXXXXX` - that value is the session token. BREEZE_API_KEY and BREEZE_API_SECRET are read
from .env; nothing is written to disk. The backend must be running (see README section "Paper trading").
"""
from __future__ import annotations

import os
import sys
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

API = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> int:
    load_dotenv()
    key, secret = os.getenv("BREEZE_API_KEY", "").strip(), os.getenv("BREEZE_API_SECRET", "").strip()
    if not key or not secret:
        print("Set BREEZE_API_KEY and BREEZE_API_SECRET in .env first (copy env.example to .env).")
        return 2
    try:
        requests.get(f"{API}/health", timeout=5).raise_for_status()
    except requests.RequestException:
        print(f"Backend not reachable at {API}. Start it first:\n"
              "  .venv\\Scripts\\python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000")
        return 2

    token = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not token:
        url = "https://api.icicidirect.com/apiuser/login?api_key=" + urllib.parse.quote_plus(key)
        print(f"Opening ICICI login: {url}\nAfter logging in, copy the apisession value from the redirect URL.")
        webbrowser.open(url)
        token = input("Session token: ").strip()
    if not token:
        return 2

    r = requests.post(f"{API}/api/login", json={"api_key": key, "api_secret": secret, "session_key": token}, timeout=60)
    body = r.json()
    if not body.get("success"):
        print(f"Login failed: {body.get('message')} {body.get('error') or ''}")
        return 1
    print(f"Logged in as {(body.get('profile') or {}).get('first_name', '?')}.")

    r = requests.post(f"{API}/api/paper/step", timeout=600)
    body = r.json()
    if not body.get("success"):
        print(f"Paper step: {body.get('message')} {body.get('error') or ''}")
        return 1
    print(f"Paper record current to {body['last_processed']} - {body['trades']} trade(s), "
          f"account {body['return_pct']:+.2f}% vs Nifty {body['benchmark_return_pct']:+.2f}%.")
    for n in body.get("notes") or []:
        print(f"  note {n['date']}: {n['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
