from __future__ import annotations

from typing import Any, Dict, Optional
from loguru import logger


def success_response(message: str = "OK", **payload: Any) -> Dict[str, Any]:
	"""Build a standard success JSON response.

	Parameters
	----------
	message: str
		Human-readable message summarizing the successful operation.
	**payload: Any
		Arbitrary key/value data to include in the response (e.g., profile, data).
	"""
	response: Dict[str, Any] = {"success": True, "message": message}
	response.update(payload)
	return response


def error_response(message: str = "Error", error: Optional[Any] = None, **payload: Any) -> Dict[str, Any]:
	"""Build a standard error JSON response.

	Parameters
	----------
	message: str
		Human-readable error message suitable for end users.
	error: Optional[Any]
		Underlying error object or text; converted to string for safety.
	**payload: Any
		Arbitrary key/value data to include in the response (e.g., code, details).
	"""
	response: Dict[str, Any] = {
		"success": False,
		"message": message,
		"error": None if error is None else str(error),
	}
	response.update(payload)
	return response


def log_exception(error: Exception, context: str = "", **extra: Any) -> None:
	"""Log an exception with context using loguru.

	Parameters
	----------
	error: Exception
		The exception instance to log.
	context: str
		Short context string describing where/why the error occurred.
	**extra: Any
		Additional structured data to attach to the log entry.
	"""
	if extra:
		logger.bind(**extra).exception(f"{context} | {error}")
	else:
		logger.exception(f"{context} | {error}")
