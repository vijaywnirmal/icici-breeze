from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..utils.response import log_exception
from ..utils.config import settings
from ..utils.ssl_config import configure_ssl_context, should_verify_ssl



@dataclass
class BreezeLoginResult:
	"""Represents the result of a Breeze login attempt."""
	success: bool
	message: str
	profile: Dict[str, Any] | None = None
	error: str | None = None


class BreezeService:
	"""Service layer encapsulating BreezeConnect usage.

	This class is responsible for:
	- Initializing BreezeConnect with an API key
	- Generating a session using API secret and session token
	- Fetching customer/profile details after successful session creation
	"""

	def __init__(self, api_key: str) -> None:
		if not api_key or not api_key.strip():
			raise ValueError("Breeze API key is required and cannot be empty")
		self._api_key = api_key.strip()
		self._client: Optional[Any] = None
		self._ssl_configured = False

	def _configure_ssl(self) -> None:
		"""Configure SSL context to handle handshake failures."""
		if not self._ssl_configured:
			configure_ssl_context()
			self._ssl_configured = True

	def _get_client(self):
		"""Lazy initialization of BreezeConnect client."""
		if self._client is None:
			self._configure_ssl()
			# Import here to avoid SSL issues during module import
			from breeze_connect import BreezeConnect
			self._client = BreezeConnect(api_key=self._api_key)
		return self._client

	@property
	def client(self):
		"""Expose the underlying BreezeConnect client (read-only) for advanced flows like websockets."""
		return self._get_client()

	def login_and_fetch_profile(self, api_secret: str, session_key: str) -> BreezeLoginResult:
		"""Generate session and fetch profile data using BreezeConnect.

		Parameters
		----------
		api_secret: str
			Breeze API secret used during session generation (required).
		session_key: str
			The "session key/token" value provided by Breeze; mapped to session_token (required).

		Returns
		-------
		BreezeLoginResult
			Structured result with success, message, profile or error.
		"""
		try:
			# Validate required parameters
			if not api_secret or not api_secret.strip():
				return BreezeLoginResult(success=False, message="API secret is required", error="Missing API secret")
			if not session_key or not session_key.strip():
				return BreezeLoginResult(success=False, message="Session key is required", error="Missing session token")
			
			# Get the client (lazy initialization)
			client = self._get_client()
				
			# 1) Generate session
			# Note: breeze-connect expects parameter name session_token (not session_key)
			client.generate_session(api_secret=api_secret.strip(), session_token=session_key.strip())

			# 2) Fetch user/customer details (profile-like data)
			profile = client.get_customer_details()
			return BreezeLoginResult(success=True, message="Login successful", profile=profile)
		except Exception as exc:  # Catch SDK/network errors and map to friendly error
			log_exception(exc, context="BreezeService.login_and_fetch_profile", api_secret_present=bool(api_secret), session_key_len=len(session_key) if session_key else 0)
			return BreezeLoginResult(success=False, message="Login failed", error=str(exc))
