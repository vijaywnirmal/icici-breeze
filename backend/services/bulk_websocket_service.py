#!/usr/bin/env python3
"""
Bulk WebSocket subscription service for all instruments.
Enables real-time feeds for all tokens in the instruments table.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from sqlalchemy import text

from ..utils.postgres import get_conn
from ..utils.response import log_exception
from ..utils.session import get_breeze, is_session_valid
from .breeze_service import BreezeService


class BulkWebSocketService:
    """Service to manage bulk WebSocket subscriptions for all instruments."""
    
    def __init__(self):
        self._breeze: Optional[BreezeService] = None
        self._connected = False
        self._subscribed_tokens: List[str] = []
        self._max_batch_size = 100  # Breeze API limit for batch subscriptions
        
    def _ensure_breeze(self) -> Optional[BreezeService]:
        """Ensure Breeze service is available and valid."""
        if self._breeze is not None:
            # Validate existing session
            if is_session_valid():
                return self._breeze
            else:
                # Session is invalid, clear it
                self._breeze = None
        
        try:
            runtime = get_breeze()
            if runtime is not None:
                # Validate the restored session
                if is_session_valid():
                    self._breeze = runtime
                    return self._breeze
                else:
                    raise RuntimeError("Restored session is invalid")
            raise RuntimeError("No active Breeze session found. Please login first.")
        except Exception as exc:
            log_exception(exc, context="BulkWebSocketService.ensure_breeze")
            raise
    
    def connect(self) -> None:
        """Connect to Breeze WebSocket."""
        if self._connected:
            return
        svc = self._ensure_breeze()
        if not svc:
            raise RuntimeError("No Breeze session available")
        try:
            svc.client.ws_connect()
            self._connected = True
        except Exception as exc:
            log_exception(exc, context="BulkWebSocketService.connect")
            raise
    
    def get_all_tokens(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all tokens from instruments table."""
        try:
            with get_conn() as conn:
                if conn is None:
                    raise RuntimeError("No database connection")
                
                query = """
                SELECT token, short_name, company_name, websocket_enabled
                FROM instruments 
                WHERE websocket_enabled = true 
                AND token IS NOT NULL 
                AND token != ''
                ORDER BY token
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                result = conn.execute(text(query))
                rows = result.fetchall()
                
                return [
                    {
                        "token": row[0],
                        "short_name": row[1],
                        "company_name": row[2],
                        "exchange_code": "NSE",  # All companies are NSE listed
                        "websocket_enabled": row[3]
                    }
                    for row in rows
                ]
        except Exception as exc:
            log_exception(exc, context="BulkWebSocketService.get_all_tokens")
            return []
    
    def format_tokens_for_subscription(self, instruments: List[Dict[str, Any]]) -> List[str]:
        """Format tokens for Breeze subscription (4.1!TOKEN format for NSE)."""
        formatted_tokens = []
        
        for inst in instruments:
            token = inst.get("token", "").strip()
            if not token:
                continue
                
            # If token is already in X.Y!TOKEN format, use as is
            if "!" in token:
                formatted_tokens.append(token)
            else:
                # All companies are NSE listed, so always use 4.1!TOKEN format
                formatted_token = f"4.1!{token}"
                formatted_tokens.append(formatted_token)
        
        return formatted_tokens
    
    def subscribe_all_tokens(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Subscribe to WebSocket feeds for all active tokens."""
        try:
            # Get all tokens from database
            instruments = self.get_all_tokens(limit)
            if not instruments:
                return {"success": False, "message": "No instruments found"}
            
            # Format tokens for subscription
            formatted_tokens = self.format_tokens_for_subscription(instruments)
            if not formatted_tokens:
                return {"success": False, "message": "No valid tokens found"}
            
            # Connect to WebSocket if not already connected
            if not self._connected:
                self.connect()
            
            # Subscribe in batches to avoid API limits
            svc = self._ensure_breeze()
            if not svc:
                return {"success": False, "message": "No Breeze session available"}
            
            subscribed_count = 0
            failed_tokens = []
            
            # Process tokens in batches
            for i in range(0, len(formatted_tokens), self._max_batch_size):
                batch = formatted_tokens[i:i + self._max_batch_size]
                try:
                    svc.client.subscribe_feeds(stock_token=batch)
                    subscribed_count += len(batch)
                    self._subscribed_tokens.extend(batch)
                except Exception as exc:
                    log_exception(exc, context="BulkWebSocketService.subscribe_batch", batch_size=len(batch))
                    failed_tokens.extend(batch)
            
            return {
                "success": True,
                "subscribed_count": subscribed_count,
                "total_tokens": len(formatted_tokens),
                "failed_count": len(failed_tokens),
                "failed_tokens": failed_tokens[:10],  # Show first 10 failed tokens
                "message": f"Successfully subscribed to {subscribed_count} tokens"
            }
            
        except Exception as exc:
            log_exception(exc, context="BulkWebSocketService.subscribe_all_tokens")
            return {"success": False, "message": str(exc)}
    
    def subscribe_sample_tokens(self, sample_size: int = 10) -> Dict[str, Any]:
        """Subscribe to a sample of tokens for testing."""
        return self.subscribe_all_tokens(limit=sample_size)
    
    def get_subscription_status(self) -> Dict[str, Any]:
        """Get current subscription status."""
        return {
            "connected": self._connected,
            "subscribed_count": len(self._subscribed_tokens),
            "subscribed_tokens": self._subscribed_tokens[:20]  # Show first 20 tokens
        }
    
    def unsubscribe_all(self) -> Dict[str, Any]:
        """Unsubscribe from all tokens."""
        try:
            if not self._subscribed_tokens:
                return {"success": True, "message": "No active subscriptions"}
            
            svc = self._ensure_breeze()
            if not svc:
                return {"success": False, "message": "No Breeze session available"}
            
            # Unsubscribe in batches
            unsubscribed_count = 0
            for i in range(0, len(self._subscribed_tokens), self._max_batch_size):
                batch = self._subscribed_tokens[i:i + self._max_batch_size]
                try:
                    svc.client.unsubscribe_feeds(stock_token=batch)
                    unsubscribed_count += len(batch)
                except Exception as exc:
                    log_exception(exc, context="BulkWebSocketService.unsubscribe_batch")
            
            self._subscribed_tokens.clear()
            
            return {
                "success": True,
                "unsubscribed_count": unsubscribed_count,
                "message": f"Unsubscribed from {unsubscribed_count} tokens"
            }
            
        except Exception as exc:
            log_exception(exc, context="BulkWebSocketService.unsubscribe_all")
            return {"success": False, "message": str(exc)}


# Global instance
BULK_WS_SERVICE = BulkWebSocketService()
