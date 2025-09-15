from __future__ import annotations

from typing import Optional, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from ..services.breeze_service import BreezeService
from ..utils.config import settings


_BREEZE: Optional[BreezeService] = None
_CUSTOMER_CACHE: Dict[str, Dict[str, Any]] = {}
_SESSION_TIMEOUT_HOURS = 24  # Sessions expire after 24 hours


def set_breeze(service: BreezeService) -> None:
	global _BREEZE
	_BREEZE = service
	# File persistence intentionally disabled


def get_breeze() -> Optional[BreezeService]:
	global _BREEZE
	
	# Return in-memory session if present
	if _BREEZE is not None:
		return _BREEZE
	
	# Try to bootstrap from environment variables
	try:
		if bootstrap_from_env():
			return _BREEZE
	except Exception:
		pass
	
	return None


def clear_session() -> None:
	"""Clear the current session (no file persistence)."""
	global _BREEZE
	_BREEZE = None


def is_session_valid() -> bool:
	"""Check if the current session is valid."""
	breeze = get_breeze()
	if not breeze:
		return False
	
	try:
		# Try to make a simple API call to validate the session
		client = breeze.client
		if hasattr(client, 'session_key') and client.session_key:
			# Try to get customer details to validate session
			client.get_customer_details()
			return True
	except Exception:
		# Session is invalid, clear it
		clear_session()
		return False
	
	return False


def bootstrap_from_env() -> bool:
	"""Initialize Breeze session from environment variables if available.

	Expects environment variables loaded via dotenv or process env:
	- BREEZE_API_KEY
	- BREEZE_API_SECRET
	- BREEZE_SESSION_TOKEN
	"""
	api_key = (settings.breeze_api_key or '').strip()
	api_secret = (settings.breeze_api_secret or '').strip()
	session_token = (settings.breeze_session_token or '').strip()
	if not api_key or not api_secret or not session_token:
		return False
	service = BreezeService(api_key=api_key)
	res = service.login_and_fetch_profile(api_secret=api_secret, session_key=session_token)
	if res and res.success:
		set_breeze(service)
		return True
	return False


# Simple in-memory cache for customer details keyed by api_session token

def get_cached_customer_details(api_session_token: str) -> Optional[Dict[str, Any]]:
	return _CUSTOMER_CACHE.get(api_session_token)


def set_cached_customer_details(api_session_token: str, details: Dict[str, Any]) -> None:
	_CUSTOMER_CACHE[api_session_token] = details


def bootstrap_from_breeze_file() -> bool:
	"""Bootstrap Breeze session from .breeze_session.json at repository root.

	The file should contain JSON with keys: api_key, api_secret, session_key.
	Returns True if session is established, otherwise False.
	"""
	global _BREEZE
	# If already initialized, nothing to do
	if _BREEZE is not None:
		return True

	# Candidate locations: CWD and project root (two levels up from this file)
	candidates = [
		Path.cwd() / ".breeze_session.json",
		Path(__file__).resolve().parents[2] / ".breeze_session.json",
	]

	session_file: Optional[Path] = next((p for p in candidates if p.is_file()), None)
	if session_file is None:
		return False

	try:
		content = json.loads(session_file.read_text(encoding="utf-8"))
		api_key = str(content.get("api_key") or "").strip()
		api_secret = str(content.get("api_secret") or "").strip()
		session_key = str(content.get("session_key") or "").strip()
		if not api_key or not api_secret or not session_key:
			return False

		service = BreezeService(api_key=api_key)
		result = service.login_and_fetch_profile(api_secret=api_secret, session_key=session_key)
		if result and result.success:
			set_breeze(service)
			return True
		return False
	except Exception:
		# Swallow errors to avoid crashing startup; caller can log
		return False

