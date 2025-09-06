from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from datetime import datetime, timezone

from ..utils.response import log_exception, success_response, error_response
from ..services.quotes_cache import upsert_quote
from ..utils.session import get_breeze

router = APIRouter(prefix="/api", tags=["nse"])


@router.get("/nse/indexes")
def get_nse_indexes(api_session: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Get NSE index data using Breeze get_quotes API."""
    try:
        breeze = get_breeze()
        
        # If no global session but api_session is provided, try to use it directly
        if not breeze and api_session:
            try:
                from ..utils.config import settings
                if settings.breeze_api_key:
                    from ..services.breeze_service import BreezeService
                    breeze = BreezeService(api_key=settings.breeze_api_key)
                    # Generate session using API secret and session token
                    breeze.client.generate_session(api_secret=settings.breeze_api_secret, session_token=api_session)
                else:
                    return error_response("API key not configured - cannot use session token")
            except Exception as exc:
                log_exception(exc, context="get_nse_indexes.create_breeze_with_session")
                return error_response("Failed to create Breeze session", error=str(exc))
        
        if not breeze:
            # Try to get cached data if no session available
            try:
                from ..services.quotes_cache import get_cached_quote
                cached_indexes = []
                
                # Check for cached data for each index
                index_tokens = ['4.1!NIFTY 50', '4.1!NIFTY BANK', '4.1!NIFTY IT']
                index_names = ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
                
                for token, name in zip(index_tokens, index_names):
                    cached = get_cached_quote(token)
                    if isinstance(cached, dict):
                        cached_indexes.append({
                            'token': token,
                            'name': name,
                            'last': cached.get('ltp'),
                            'change': None,  # We don't have change in cache
                            'percentChange': cached.get('change_pct'),
                            'close': cached.get('close'),
                            'timestamp': cached.get('updated_at'),
                            'stock_name': name,
                            'status': 'cached'
                        })
                
                if cached_indexes:
                    return success_response({
                        'indexes': cached_indexes,
                        'count': len(cached_indexes),
                        'source': 'cache',
                        'message': 'Using cached data - please login for live data'
                    })
                
            except Exception as cache_exc:
                log_exception(cache_exc, context="get_nse_indexes.cache_fallback")
            
            return error_response("Breeze session not available - please login first")
        
        # Define the indexes with their Breeze parameters
        # Note: Only NIFTY is currently working with the API
        indexes_config = [
            {
                'token': '4.1!NIFTY 50',
                'name': 'NIFTY',
                'stock_code': 'NIFTY',
                'exchange_code': 'NSE',
                'expiry_date': '',
                'product_type': 'cash',
                'right': '',
                'strike_price': ''
            },
            {
                'token': '4.1!NIFTY BANK',
                'name': 'BANKNIFTY',
                'stock_code': 'CNXBAN',
                'exchange_code': 'NSE',
                'expiry_date': '',
                'product_type': 'cash',
                'right': '',
                'strike_price': ''
            },
            {
                'token': '4.1!NIFTY FIN SERVICE',
                'name': 'FINNIFTY',
                'stock_code': 'NIFFIN',
                'exchange_code': 'NSE',
                'expiry_date': '',
                'product_type': 'cash',
                'right': '',
                'strike_price': ''
            }
        ]
        
        formatted_indexes = []
        
        for index_config in indexes_config:
            try:
                # Add delay to avoid rate limiting
                if index_config != indexes_config[0]:  # Skip delay for first index
                    import time
                    time.sleep(1.0)  # 1 second delay between calls
                
                # Call Breeze get_quotes API
                response = breeze.client.get_quotes(
                    stock_code=index_config['stock_code'],
                    exchange_code=index_config['exchange_code'],
                    expiry_date=index_config['expiry_date'],
                    product_type=index_config['product_type'],
                    right=index_config['right'],
                    strike_price=index_config['strike_price']
                )
                
                # Check for error responses
                if isinstance(response, dict) and response.get('Error'):
                    log_exception(Exception(f"API Error for {index_config['stock_code']}: {response.get('Error')}"), context="get_nse_indexes.api_error")
                
                if isinstance(response, dict) and response.get('Success'):
                    success_data = response['Success']
                    if isinstance(success_data, list) and len(success_data) > 0:
                        # Find the NSE data (first item with exchange_code = 'NSE')
                        data = None
                        for item in success_data:
                            if item.get('exchange_code') == 'NSE':
                                data = item
                                break
                        
                        if data:
                            index_data = {
                                'token': index_config['token'],
                                'name': index_config['name'],
                                'last': data.get('ltp'),
                                'change': data.get('ltp') - data.get('previous_close', 0) if data.get('ltp') and data.get('previous_close') else None,
                                'percentChange': data.get('ltp_percent_change'),
                                'close': data.get('previous_close'),
                                'open': data.get('open'),
                                'high': data.get('high'),
                                'low': data.get('low'),
                                'timestamp': data.get('ltt'),
                                'stock_name': index_config['name']
                            }
                            
                            formatted_indexes.append(index_data)
                        
                        # Cache the data in ltp_cache table
                        try:
                            cache_payload = {
                                'ltp': index_data['last'],
                                'close': index_data['close'],
                                'change_pct': index_data['percentChange'],
                                'bid': None,
                                'ask': None,
                                'volume': None,
                                'data': response,
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            }
                            upsert_quote(symbol=index_config['token'], payload=cache_payload)
                        except Exception as cache_exc:
                            log_exception(cache_exc, context="get_nse_indexes.cache", symbol=index_config['token'])
                            
            except Exception as index_exc:
                log_exception(index_exc, context="get_nse_indexes.index", symbol=index_config['name'])
                continue
        
        return success_response({
            'indexes': formatted_indexes,
            'count': len(formatted_indexes)
        })
        
    except Exception as exc:
        log_exception(exc, context="get_nse_indexes")
        return error_response("Failed to fetch NSE index data", error=str(exc))
