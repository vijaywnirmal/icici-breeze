from fastapi import APIRouter, Query, BackgroundTasks
from pydantic import BaseModel, Field

from ..services.breeze_service import BreezeService
from ..utils.session import set_breeze
from ..utils.response import success_response, error_response, log_exception
from ..utils.config import settings
from ..utils.session import get_breeze
from ..utils.session import get_cached_customer_details, set_cached_customer_details


router = APIRouter(prefix="/api", tags=["auth"])


class LoginPayload(BaseModel):
    """Incoming login payload with required credential fields."""
    api_key: str = Field(..., description="Breeze API Key (required)")
    api_secret: str = Field(..., description="Breeze API Secret (required)")
    session_key: str = Field(..., description="Breeze Session Key/Token (required)")


@router.post("/login")
def login(payload: LoginPayload, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Attempt a Breeze login and return profile information on success."""
    # Validate that all credentials are provided and non-empty
    if not payload.api_key.strip():
        return error_response("API Key is required and cannot be empty")
    if not payload.api_secret.strip():
        return error_response("API Secret is required and cannot be empty")  
    if not payload.session_key.strip():
        return error_response("Session Key is required and cannot be empty")
        
    try:
        service = BreezeService(api_key=payload.api_key.strip())
        result = service.login_and_fetch_profile(
            api_secret=payload.api_secret.strip(),
            session_key=payload.session_key.strip(),
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

    # First-run: ensure instruments table exists and populate if empty (background)
    try:
        if settings.instruments_first_run_on_login:
            from ..utils.instruments_first_run import ensure_instruments_first_run
            background_tasks.add_task(ensure_instruments_first_run)
    except Exception as _exc:
        # Non-fatal for login flow; log and continue
        log_exception(_exc, context="login.ensure_instruments_first_run")

    # New: run daily refresh on first login of the day (idempotent)
    try:
        from ..utils.daily_refresh import run_daily_refresh_if_needed
        background_tasks.add_task(run_daily_refresh_if_needed)
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
        if service is None:
            return error_response("Not logged in. Please login first with your credentials.")

        # Call Breeze SDK (use provided token or default session)
        try:
            if api_session:
                profile = service.client.get_customer_details(api_session=api_session)
            else:
                profile = service.client.get_customer_details()
        except Exception as exc:
            log_exception(exc, context="login.profile.get_customer_details")
            return error_response("Failed to fetch profile", error=str(exc))

        # Normalize data shape and extract customer details
        data = profile.get("Success") if isinstance(profile, dict) and "Success" in profile else profile
        full_name = ""
        if isinstance(data, dict):
            full_name = str(data.get("idirect_user_name") or "").strip()
        first_name = full_name.split()[0].title() if full_name else ""
        
        # Return full profile data including all customer details from the raw JSON response
        # This includes fields like idirect_user_name, email_id, user_id, pan, etc.
        return success_response("Profile", first_name=first_name, profile=profile)
    except Exception as exc:
        log_exception(exc, context="login.profile")
        return error_response("Unexpected error", error=str(exc))


@router.get("/account/details")
def account_details(api_session: str | None = Query(None)) -> dict[str, object]:
    """Return cached customer details if available; otherwise fetch and cache.

    The response format aligns with frontend expectations: `{ success, customer }`.
    """
    try:
        # 1) Serve from cache if present
        cached = get_cached_customer_details(api_session) if api_session else None
        if cached is not None:
            return success_response("Customer details", customer=cached)

        # 2) Acquire BreezeService
        service: BreezeService | None = get_breeze()
        if service is None:
            return error_response("Not logged in. Please login first with your credentials.")

        # 3) Fetch details using provided token or default session
        try:
            if api_session:
                details = service.client.get_customer_details(api_session=api_session)
            else:
                details = service.client.get_customer_details()
        except Exception as exc:
            log_exception(exc, context="account.details.get_customer_details")
            return error_response("Failed to fetch customer details", error=str(exc))

        # 4) Normalize to inner 'Success' payload if present and cache
        payload = details.get("Success") if isinstance(details, dict) and "Success" in details else details
        if isinstance(payload, dict) and api_session:
            try:
                set_cached_customer_details(api_session, payload)
            except Exception:
                pass

        return success_response("Customer details", customer=payload or details)
    except Exception as exc:
        log_exception(exc, context="login.account_details")
        return error_response("Unexpected error", error=str(exc))
