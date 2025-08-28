from fastapi import APIRouter

from ..models.hello import HelloResponse


router = APIRouter(prefix="/api", tags=["public"])


@router.get("/hello", response_model=HelloResponse)
def say_hello() -> HelloResponse:
    return HelloResponse(message="Hello, Automated Trading Platform is running!")



