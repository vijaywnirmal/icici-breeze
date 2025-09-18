from __future__ import annotations

import os
from typing import Optional

try:
	import redis  # type: ignore
except Exception:
	redis = None  # Graceful fallback when Redis client is not installed

_redis: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
	"""Return a shared Redis connection if REDIS_URL is present.

	Accepts env:
	- REDIS_URL (e.g. redis://localhost:6379/0)
	- Or REDIS_HOST/REDIS_PORT/REDIS_DB
	"""
	global _redis
	if _redis is not None:
		return _redis

	# If redis library isn't available, skip
	if redis is None:
		return None

	url = os.environ.get("REDIS_URL", "").strip()
	if url:
		_redis = redis.from_url(url, decode_responses=True)
		return _redis

	host = os.environ.get("REDIS_HOST", "").strip() or None
	if host:
		port = int(os.environ.get("REDIS_PORT", "6379"))
		db = int(os.environ.get("REDIS_DB", "0"))
		_redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)
		return _redis

	return None


