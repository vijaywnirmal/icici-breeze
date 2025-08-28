from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.breeze_service import BreezeService
from ..utils.response import success_response, error_response


router = APIRouter(prefix="/api", tags=["auth"])


class LoginPayload(BaseModel):
	"""Incoming login payload with credential fields.

	All fields are required and minimally validated for non-empty content.
	"""
	api_key: str = Field(..., min_length=1, description="Breeze API Key")
	api_secret: str = Field(..., min_length=1, description="Breeze API Secret")
	session_key: str = Field(..., min_length=1, description="Breeze Session Key/Token")


@router.post("/login")
def login(payload: LoginPayload) -> dict:
	"""Attempt a Breeze login and return profile information on success.

	- Validates payload
	- Uses BreezeService to generate a session and fetch profile
	- Returns consistent JSON success/error response
	"""
	service = BreezeService(api_key=payload.api_key)
	result = service.login_and_fetch_profile(api_secret=payload.api_secret, session_key=payload.session_key)

	if not result.success:
		return error_response("Login failed", error=result.error)

	return success_response("Login successful", profile=result.profile)
