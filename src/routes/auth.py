from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
	breeze_api_key: str
	breeze_api_secret: str
	breeze_session_token: str


class LoginResponse(BaseModel):
	success: bool
	message: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
	if not payload.breeze_api_key or not payload.breeze_api_secret or not payload.breeze_session_token:
		raise HTTPException(status_code=400, detail="All credentials are required.")

	# Placeholder: later we will initialize Breeze client and validate credentials
	return LoginResponse(success=True, message="Credentials received.")


