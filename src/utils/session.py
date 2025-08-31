from __future__ import annotations

from typing import Optional, Dict, Any

from ..services.breeze_service import BreezeService


_BREEZE: Optional[BreezeService] = None
_CUSTOMER_CACHE: Dict[str, Dict[str, Any]] = {}


def set_breeze(service: BreezeService) -> None:
	global _BREEZE
	_BREEZE = service


def get_breeze() -> Optional[BreezeService]:
	return _BREEZE



# Simple in-memory cache for customer details keyed by api_session token
def get_cached_customer_details(api_session_token: str) -> Optional[Dict[str, Any]]:
	return _CUSTOMER_CACHE.get(api_session_token)


def set_cached_customer_details(api_session_token: str, details: Dict[str, Any]) -> None:
	_CUSTOMER_CACHE[api_session_token] = details


