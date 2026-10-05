#!/usr/bin/env python3
"""Hand today's Breeze session to the running backend, then bring the paper record up to date.

    .venv\\Scripts\\python daily_login.py            # opens ICICI's login page, then asks for the session token
    .venv\\Scripts\\python daily_login.py TOKEN      # if you already have today's token

(Or do the same from the nifty-reels studio: Trading tab -> Log in to Breeze.)
Logging in after the close also starts nifty-reels' "18 Options Replay" job, so the day's replay posts even
if its scheduled check window is already over.
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
REPLAY_TASK = os.environ.get("REPLAY_TASK", r"\NiftyReels\18 Options Replay")  # nifty-reels' replay job


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
    post_todays_replay(body["last_processed"])
    return 0


def post_todays_replay(last_processed: str) -> None:
    """Logged in after the close: ask nifty-reels to post today's replay now (its scheduled check window
    may already be over). Runs that job via Task Scheduler; does nothing if nifty-reels isn't set up."""
    import datetime as dt
    import subprocess
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30))).date().isoformat()
    if last_processed != today:
        return  # during the day: the regular check window picks the trade up after the close
    r = subprocess.run(["schtasks", "/Run", "/TN", REPLAY_TASK], capture_output=True, text=True)
    print("Posting today's replay (if it traded)." if r.returncode == 0 else
          f"Couldn't start {REPLAY_TASK}: {(r.stderr or r.stdout).strip()}")


if __name__ == "__main__":
    sys.exit(main())
