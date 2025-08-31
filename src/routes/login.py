from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..services.breeze_service import BreezeService
from ..utils.session import set_breeze
from ..utils.response import success_response, error_response, log_exception
from ..utils.config import settings
from ..utils.session import get_breeze


router = APIRouter(prefix="/api", tags=["auth"])


class LoginPayload(BaseModel):
    """Incoming login payload with optional credential fields.

    If omitted, server-side environment variables will be used.
    """
    api_key: str | None = Field(None, description="Breeze API Key (optional)")
    api_secret: str | None = Field(None, description="Breeze API Secret (optional)")
    session_key: str | None = Field(None, description="Breeze Session Key/Token (optional)")


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


@router.get("/profile")
def get_profile(api_session: str | None = Query(None)) -> dict[str, object]:
    """Return Breeze profile details; optionally use provided api_session token.

    If runtime BreezeService is available (from prior login), use it; otherwise, try
    environment credentials as a fallback. Extract and return first_name for UI.
    """
    try:
        service: BreezeService | None = get_breeze()
        profile = None
        if service is None:
            # Minimal fallback: if API key available, create client and use provided api_session directly
            if settings.breeze_api_key:
                try:
                    service = BreezeService(api_key=settings.breeze_api_key)
                except Exception:
                    service = None
        # If still no service, try full env login only if all creds present
        if service is None and settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
            svc = BreezeService(api_key=settings.breeze_api_key)
            res = svc.login_and_fetch_profile(api_secret=settings.breeze_api_secret, session_key=settings.breeze_session_token)
            if res.success:
                service = svc
                profile = res.profile
        if service is None:
            return error_response("Not logged in and no server credentials available")

        # Call Breeze SDK only if a profile wasn't already fetched during env login
        try:
            if profile is None:
                if api_session:
                    profile = service.client.get_customer_details(api_session=api_session)
                else:
                    profile = service.client.get_customer_details()
        except Exception as exc:
            log_exception(exc, context="login.profile.get_customer_details")
            return error_response("Failed to fetch profile", error=str(exc))

        # Normalize data shape and extract first name
        data = profile.get("Success") if isinstance(profile, dict) and "Success" in profile else profile
        full_name = ""
        if isinstance(data, dict):
            full_name = str(data.get("idirect_user_name") or "").strip()
        first_name = full_name.split()[0].title() if full_name else ""
        return success_response("Profile", first_name=first_name, profile=profile)
    except Exception as exc:
        log_exception(exc, context="login.profile")
        return error_response("Unexpected error", error=str(exc))
