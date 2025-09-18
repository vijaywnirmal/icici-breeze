from __future__ import annotations

from typing import Optional, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from ..services.breeze_service import BreezeService
from ..utils.config import settings
<<<<<<< HEAD
from .redis_config import (
    cache_session, get_cached_session, cache_set, cache_get, 
    cache_delete, is_redis_available, CacheKeys, make_key
)
=======
from .redis_client import get_redis
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3


_BREEZE: Optional[BreezeService] = None
_CUSTOMER_CACHE: Dict[str, Dict[str, Any]] = {}
_SESSION_TIMEOUT_HOURS = 24  # Sessions expire after 24 hours


def set_breeze(service: BreezeService) -> None:
	global _BREEZE
	_BREEZE = service
<<<<<<< HEAD
	
	# Cache session data in Redis if available
	if is_redis_available() and hasattr(service, 'client') and service.client:
		try:
			session_data = {
				'api_key': service.client.api_key,
				'session_key': getattr(service.client, 'session_key', ''),
				'customer_id': getattr(service.client, 'customer_id', ''),
				'created_at': datetime.utcnow().isoformat(),
				'profile': getattr(service, 'profile', {})
			}
			cache_session('current', session_data, _SESSION_TIMEOUT_HOURS * 3600)
		except Exception:
			pass  # Continue without Redis caching
=======
	# File persistence intentionally disabled
	# Persist minimal session into Redis for cross-process resilience
	try:
		r = get_redis()
		if r is not None and service is not None and getattr(service, 'client', None):
			client = service.client
			session_key = getattr(client, 'session_key', None)
			api_key = getattr(client, 'api_key', None) if hasattr(client, 'api_key') else None
			if session_key:
				payload = {"api_key": api_key, "session_key": session_key}
				r.setex("session:active", 86400, json.dumps(payload))
	except Exception:
		pass
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3


def get_breeze() -> Optional[BreezeService]:
	global _BREEZE
	
	# Return in-memory session if present
	if _BREEZE is not None:
		return _BREEZE
	
	# Try to restore from Redis cache
	if is_redis_available():
		try:
			cached_session = get_cached_session('current')
			if cached_session and _restore_from_cache(cached_session):
				return _BREEZE
		except Exception:
			pass  # Continue to other methods
	
	# Try to bootstrap from environment variables
	try:
		# Prefer Redis snapshot first
		if bootstrap_from_redis():
			return _BREEZE
		if bootstrap_from_env():
			return _BREEZE
	except Exception:
		pass
	
	return None


def clear_session() -> None:
	"""Clear the current session (no file persistence)."""
	global _BREEZE
	_BREEZE = None
<<<<<<< HEAD
	
	# Clear from Redis cache as well
	if is_redis_available():
		try:
			cache_delete(make_key(CacheKeys.SESSION, 'current'))
		except Exception:
			pass
=======
	# Also remove Redis snapshot
	try:
		r = get_redis()
		if r is not None:
			r.delete("session:active")
	except Exception:
		pass
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3


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


<<<<<<< HEAD
def _restore_from_cache(cached_session: Dict[str, Any]) -> bool:
	"""Restore BreezeService from cached session data."""
	try:
		from ..services.breeze_service import BreezeService
		
		api_key = cached_session.get('api_key')
		session_key = cached_session.get('session_key')
		customer_id = cached_session.get('customer_id')
		profile = cached_session.get('profile', {})
		
		if not api_key or not session_key:
			return False
		
		# Create new service instance
		service = BreezeService(api_key=api_key)
		
		# Set session key directly
		if hasattr(service.client, 'session_key'):
			service.client.session_key = session_key
		if hasattr(service.client, 'customer_id'):
			service.client.customer_id = customer_id
		
		# Set profile if available
		if profile:
			service.profile = profile
		
		# Set the global instance
		global _BREEZE
		_BREEZE = service
		
		return True
	except Exception:
		return False
=======
def bootstrap_from_redis() -> bool:
	"""Initialize Breeze session from Redis snapshot if present."""
	try:
		r = get_redis()
		if r is None:
			return False
		raw = r.get("session:active")
		if not raw:
			return False
		data = json.loads(raw)
		api_key = (data.get("api_key") or settings.breeze_api_key or '').strip()
		session_key = (data.get("session_key") or settings.breeze_session_token or '').strip()
		api_secret = (settings.breeze_api_secret or '').strip()
		if not api_key or not session_key or not api_secret:
			return False
		service = BreezeService(api_key=api_key)
		res = service.login_and_fetch_profile(api_secret=api_secret, session_key=session_key)
		if res and res.success:
			set_breeze(service)
			return True
		return False
	except Exception:
		return False


# Simple in-memory cache for customer details keyed by api_session token
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3


# Enhanced customer details caching with Redis fallback
def get_cached_customer_details(api_session_token: str) -> Optional[Dict[str, Any]]:
	# Try Redis first
<<<<<<< HEAD
	if is_redis_available():
		try:
			cached = cache_get(make_key(CacheKeys.USER_PROFILE, api_session_token))
			if cached:
				return cached
		except Exception:
			pass
	
	# Fallback to in-memory cache
=======
	try:
		r = get_redis()
		if r is not None and api_session_token:
			key = f"customer:{api_session_token}"
			raw = r.get(key)
			if raw:
				return json.loads(raw)
	except Exception:
		pass

>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3
	return _CUSTOMER_CACHE.get(api_session_token)


def set_cached_customer_details(api_session_token: str, details: Dict[str, Any]) -> None:
	# Store in in-memory cache
	_CUSTOMER_CACHE[api_session_token] = details
<<<<<<< HEAD
	
	# Also store in Redis if available
	if is_redis_available():
		try:
			cache_set(make_key(CacheKeys.USER_PROFILE, api_session_token), details, 3600)  # 1 hour TTL
		except Exception:
			pass
=======
	# Also write to Redis with TTL (1 hour)
	try:
		r = get_redis()
		if r is not None and api_session_token:
			key = f"customer:{api_session_token}"
			r.setex(key, 3600, json.dumps(details))
	except Exception:
		pass


def purge_session_and_caches(api_session_token: Optional[str] = None) -> None:
	"""Remove active session snapshot and clear cached customer details.

	If api_session_token is provided, remove only that customer's cache; otherwise clear all.
	"""
	clear_session()
	# In-memory cache purge
	try:
		if api_session_token:
			_CUSTOMER_CACHE.pop(api_session_token, None)
		else:
			_CUSTOMER_CACHE.clear()
	except Exception:
		pass
	# Redis cache purge
	try:
		r = get_redis()
		if r is not None:
			if api_session_token:
				r.delete(f"customer:{api_session_token}")
			else:
				# Best-effort wildcard cleanup
				for key in r.scan_iter(match="customer:*"):
					r.delete(key)
	except Exception:
		pass
>>>>>>> 5c637c62df39be05dea64d026b57124ad9477fe3



