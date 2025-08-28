from __future__ import annotations

from typing import Any, Optional
from importlib import import_module

from .config import settings
from .response import log_exception


_CLIENT: Optional[Any] = None  # Avoid hard dependency on supabase types


def get_supabase() -> Optional[Any]:
	"""Return a Supabase client if supabase SDK and env are available.

	This function lazily imports the SDK to avoid crashing when the package is
	missing. Returns None if not configured or import fails.
	"""
	global _CLIENT
	if _CLIENT is not None:
		return _CLIENT
	try:
		if settings.supabase_url and settings.supabase_key:
			# Lazy import to keep supabase optional at runtime
			mod = import_module("supabase")
			create_client = getattr(mod, "create_client", None)
			if not create_client:
				return None
			_CLIENT = create_client(settings.supabase_url, settings.supabase_key)
			return _CLIENT
	except Exception as exc:
		log_exception(exc, context="supabase.get_supabase")
	return None


