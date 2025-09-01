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
    """Incoming login payload with optional credential fields.

    If omitted, server-side environment variables will be used.
    """
    api_key: str | None = Field(None, description="Breeze API Key (optional)")
    api_secret: str | None = Field(None, description="Breeze API Secret (optional)")
    session_key: str | None = Field(None, description="Breeze Session Key/Token (optional)")


@router.post("/login")
def login(payload: LoginPayload, background_tasks: BackgroundTasks) -> dict[str, object]:
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

    # First-run: ensure instruments table exists and populate if empty (background)
    try:
        if settings.instruments_first_run_on_login:
            from ..utils.instruments_first_run import ensure_instruments_first_run
            background_tasks.add_task(ensure_instruments_first_run)
            # Also refresh Nifty 50 list on first login of the day (idempotent)
            try:
                from ..utils.nifty50_service import refresh_nifty50_list
                background_tasks.add_task(refresh_nifty50_list)
            except Exception:
                pass
    except Exception as _exc:
        # Non-fatal for login flow; log and continue
        log_exception(_exc, context="login.ensure_instruments_first_run")

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
            # Prefer full env login if all creds present
            if settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
                svc = BreezeService(api_key=settings.breeze_api_key)
                res = svc.login_and_fetch_profile(
                    api_secret=settings.breeze_api_secret,
                    session_key=settings.breeze_session_token,
                )
                if res.success:
                    service = svc
            # If not, but we have an API key, still construct client (useful when api_session is provided)
            elif settings.breeze_api_key:
                try:
                    service = BreezeService(api_key=settings.breeze_api_key)
                except Exception:
                    service = None
        if service is None:
            return error_response("Not logged in and no server credentials available")

        # Call Breeze SDK (prefer provided token; else server token)
        try:
            session_to_use = api_session or (settings.breeze_session_token or None)
            if not session_to_use:
                return error_response("API Session cannot be empty and no server session configured")
            profile = service.client.get_customer_details(api_session=session_to_use)
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
        if service is None and settings.breeze_api_key:
            try:
                service = BreezeService(api_key=settings.breeze_api_key)
            except Exception:
                service = None
        if service is None and settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
            svc = BreezeService(api_key=settings.breeze_api_key)
            res = svc.login_and_fetch_profile(api_secret=settings.breeze_api_secret, session_key=settings.breeze_session_token)
            if res.success:
                service = svc
        if service is None:
            return error_response("Not logged in and no server credentials available")

        # 3) Fetch details using provided token; else server token
        try:
            session_to_use = api_session or (settings.breeze_session_token or None)
            if not session_to_use:
                return error_response("API Session cannot be empty and no server session configured")
            details = service.client.get_customer_details(api_session=session_to_use)
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
