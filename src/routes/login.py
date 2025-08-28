from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services.breeze_service import BreezeService
from ..utils.session import set_breeze
from ..utils.response import success_response, error_response


router = APIRouter(prefix="/api", tags=["auth"])


class LoginPayload(BaseModel):
    """Incoming login payload with credential fields."""
    api_key: str = Field(..., min_length=1, description="Breeze API Key")
    api_secret: str = Field(..., min_length=1, description="Breeze API Secret")
    session_key: str = Field(..., min_length=1, description="Breeze Session Key/Token")


@router.post("/login")
def login(payload: LoginPayload) -> dict[str, object]:
    """Attempt a Breeze login and return profile information on success."""
    try:
        service = BreezeService(api_key=payload.api_key)
        result = service.login_and_fetch_profile(
            api_secret=payload.api_secret,
            session_key=payload.session_key,
        )
    except Exception as exc:
        return error_response("Exception during login", error=str(exc))

    if not result.success:
        return error_response("Login failed", error=result.error)

    # Store the Breeze session for subsequent API/WS usage
    try:
        set_breeze(service)
    except Exception:
        pass

    # Optional: sanitize profile dict here
    return success_response("Login successful", profile=result.profile)
