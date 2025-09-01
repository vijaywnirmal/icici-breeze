from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..utils.postgres import get_conn
from ..utils.response import error_response, success_response, log_exception


router = APIRouter(prefix="/api", tags=["instruments"])


@router.get("/instruments/lookup")
def instruments_lookup(tokens: str = Query(..., description="Comma-separated list of tokens"), exchange: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Resolve ICICI tokens to symbol/company/exchange from instruments table.

    Example: /api/instruments/lookup?tokens=800078,10515
    """
    try:
        token_list = [t.strip() for t in (tokens or "").split(",") if t.strip()]
        if not token_list:
            return error_response("No tokens provided")

        where = "token = ANY(:tokens)"
        params: Dict[str, Any] = {"tokens": token_list}
        if exchange:
            where += " AND exchange = :exchange"
            params["exchange"] = exchange.upper()

        sql = text(
            f"SELECT token, symbol, company_name, series, isin, lot_size, exchange FROM instruments WHERE {where}"
        )

        with get_conn() as conn:
            if conn is None:
                return error_response("Database not configured")
            rows = conn.execute(sql, params).fetchall()
            items = [
                {
                    "token": r[0],
                    "symbol": r[1],
                    "company_name": r[2],
                    "series": r[3],
                    "isin": r[4],
                    "lot_size": r[5],
                    "exchange": r[6],
                }
                for r in rows
            ]
            return success_response("Instruments lookup", items=items)
    except Exception as exc:
        log_exception(exc, context="instruments.lookup")
        return error_response("Failed to lookup instruments", error=str(exc))


def _example_join_trades() -> str:
    """Illustrative SQL for joining trades/orders that store token to instruments.

    This is not executed here but provided for reference.
    """
    return (
        "SELECT t.trade_id, i.symbol, i.company_name, i.exchange "
        "FROM trades t JOIN instruments i ON t.token = i.token"
    )


