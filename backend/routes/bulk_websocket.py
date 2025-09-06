"""
API routes for bulk WebSocket subscription management.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..services.bulk_websocket_service import BULK_WS_SERVICE

router = APIRouter(prefix="/api/bulk-websocket", tags=["bulk-websocket"])


@router.post("/subscribe-all")
async def subscribe_all_tokens(limit: Optional[int] = Query(None, description="Limit number of tokens to subscribe")):
    """Subscribe to WebSocket feeds for all active tokens."""
    try:
        result = BULK_WS_SERVICE.subscribe_all_tokens(limit)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe-sample")
async def subscribe_sample_tokens(sample_size: int = Query(10, description="Number of sample tokens to subscribe")):
    """Subscribe to a sample of tokens for testing."""
    try:
        result = BULK_WS_SERVICE.subscribe_sample_tokens(sample_size)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_subscription_status():
    """Get current subscription status."""
    try:
        return BULK_WS_SERVICE.get_subscription_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe-all")
async def unsubscribe_all_tokens():
    """Unsubscribe from all tokens."""
    try:
        result = BULK_WS_SERVICE.unsubscribe_all()
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tokens")
async def get_available_tokens(limit: Optional[int] = Query(50, description="Limit number of tokens to return")):
    """Get list of available tokens from instruments table."""
    try:
        tokens = BULK_WS_SERVICE.get_all_tokens(limit)
        return {
            "success": True,
            "count": len(tokens),
            "tokens": tokens
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
