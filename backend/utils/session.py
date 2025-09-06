from __future__ import annotations

from typing import Optional, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from ..services.breeze_service import BreezeService


_BREEZE: Optional[BreezeService] = None
_CUSTOMER_CACHE: Dict[str, Dict[str, Any]] = {}
_SESSION_FILE = Path("session_data.json")
_SESSION_TIMEOUT_HOURS = 24  # Sessions expire after 24 hours


def set_breeze(service: BreezeService) -> None:
	global _BREEZE
	_BREEZE = service
	# Disabled file persistence per request


def get_breeze() -> Optional[BreezeService]:
	global _BREEZE
	
	# If we have a session in memory, return it
	if _BREEZE is not None:
		return _BREEZE
	
	# File-based restore disabled
	return None


def clear_session() -> None:
	"""Clear the current session and remove saved session file."""
	global _BREEZE
	_BREEZE = None
	
	try:
		if _SESSION_FILE.exists():
			_SESSION_FILE.unlink()
	except Exception:
		pass


def is_session_valid() -> bool:
	"""Check if the current session is valid."""
	breeze = get_breeze()
	if not breeze:
		return False
	
	try:
		# Try to make a simple API call to validate the session
		client = breeze.client
		if hasattr(client, 'session_token') and client.session_token:
			# Try to get customer details to validate session
			client.get_customer_details()
			return True
	except Exception:
		# Session is invalid, clear it
		clear_session()
		return False
	
	return False


# Simple in-memory cache for customer details keyed by api_session token
def get_cached_customer_details(api_session_token: str) -> Optional[Dict[str, Any]]:
	return _CUSTOMER_CACHE.get(api_session_token)


def set_cached_customer_details(api_session_token: str, details: Dict[str, Any]) -> None:
	_CUSTOMER_CACHE[api_session_token] = details


