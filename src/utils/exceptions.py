from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
	"""Base application error with optional context payload."""

	def __init__(self, message: str, *, context: Optional[dict[str, Any]] = None, cause: Optional[BaseException] = None) -> None:
		super().__init__(message)
		self.context = context or {}
		self.__cause__ = cause  # proper exception chaining


class ValidationError(AppError):
	"""Input validation error (business logic)."""


class DataUnavailableError(AppError):
	"""Required data missing or not available."""


class ExternalServiceError(AppError):
	"""External dependency failure (e.g., Breeze API)."""


class TransientError(AppError):
	"""Transient recoverable error; retry may succeed."""


