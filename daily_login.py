#!/usr/bin/env python3
"""Hand today's Breeze session to the running backend, then bring the paper record up to date.

    .venv\\Scripts\\python daily_login.py            # opens ICICI's login page, then asks for the session token
    .venv\\Scripts\\python daily_login.py TOKEN      # if you already have today's token

(Or do the same from the nifty-reels studio: Trading tab -> Log in to Breeze.)
Breeze sessions last a day. After you log in on ICICI's page it redirects to your app's redirect URL with
`?apisession=XXXXXXXX` - that value is the session token. The backend reads BREEZE_API_KEY and
BREEZE_API_SECRET from its own .env; only the token passes through here, and nothing is written to disk.
"""
from __future__ import annotations

import os
import sys
import webbrowser

import requests

API = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> int:
    try:
        requests.get(f"{API}/health", timeout=5).raise_for_status()
    except requests.RequestException:
        print(f"Backend not reachable at {API}. It starts at logon (task '19 Breeze Backend'), or run:\n"
              "  .venv\\Scripts\\pythonw.exe serve.py")
        return 2

    token = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if not token:
        r = requests.get(f"{API}/api/paper/login-url", timeout=10).json()
        if not r.get("success"):
            print(r.get("message"))
            return 2
        print(f"Opening ICICI login: {r['url']}\nAfter logging in, copy the apisession value from the redirect URL.")
        webbrowser.open(r["url"])
        token = input("Session token: ").strip()
    if not token:
        return 2

    body = requests.post(f"{API}/api/paper/login", json={"session_token": token}, timeout=600).json()
    if not body.get("success"):
        print(f"Login failed: {body.get('message')} {body.get('error') or ''}")
        return 1
    print(f"Logged in as {body.get('name') or '?'}.")
    if body.get("step_error"):
        print(f"Paper step failed: {body['step_error']}")
        return 1
    print(f"Paper record current to {body['last_processed']} - {body['trades']} trade(s), "
          f"account {body['return_pct']:+.2f}% vs Nifty {body['benchmark_return_pct']:+.2f}%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
