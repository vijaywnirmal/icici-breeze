from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from breeze_connect import BreezeConnect
from ..utils.response import log_exception


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
		self._client = BreezeConnect(api_key=api_key)

	@property
	def client(self) -> BreezeConnect:
		"""Expose the underlying BreezeConnect client (read-only) for advanced flows like websockets."""
		return self._client

	def login_and_fetch_profile(self, api_secret: str, session_key: str) -> BreezeLoginResult:
		"""Generate session and fetch profile data using BreezeConnect.

		Parameters
		----------
		api_secret: str
			Breeze API secret used during session generation.
		session_key: str
			The "session key/token" value provided by Breeze; mapped to session_token.

		Returns
		-------
		BreezeLoginResult
			Structured result with success, message, profile or error.
		"""
		try:
			# 1) Generate session
			# Note: breeze-connect expects parameter name session_token (not session_key)
			self._client.generate_session(api_secret=api_secret, session_token=session_key)

			# 2) Fetch user/customer details (profile-like data)
			profile = self._client.get_customer_details()
			return BreezeLoginResult(success=True, message="Login successful", profile=profile)
		except Exception as exc:  # Catch SDK/network errors and map to friendly error
			log_exception(exc, context="BreezeService.login_and_fetch_profile", api_secret_present=bool(api_secret), session_key_len=len(session_key))
			return BreezeLoginResult(success=False, message="Login failed", error=str(exc))
