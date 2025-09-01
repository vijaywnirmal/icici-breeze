from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import text

from .postgres import get_conn, ensure_tables


def _normalize_symbol(val: Any) -> str:
    try:
        s = str(val or "").strip().upper()
        if s.endswith(".NS"):
            s = s[:-3]
        return s
    except Exception:
        return ""


def _fetch_nifty50_df():
    df = None
    err: Optional[Exception] = None
    try:
        from nselib.nse import nifty50_stock_list as get_list  # type: ignore
        df = get_list()
    except Exception as e:
        err = e
        try:
            from nselib.capital_market import nifty50_equity_list as get_list_alt  # type: ignore
            df = get_list_alt()
        except Exception as e2:
            err = e2
    if df is None and err is not None:
        logger.exception("Failed to fetch Nifty50 list: {}", err)
    return df


def refresh_nifty50_list() -> int:
    """Fetch Nifty50 constituents and upsert into nifty50_list, mapping stock_code from instruments.

    Returns number of rows written.
    """
    ensure_tables()
    df = _fetch_nifty50_df()
    if df is None:
        return 0

    cols = {str(c).lower(): c for c in df.columns}
    sym_col = cols.get('symbol') or cols.get('symbol_name') or list(cols.values())[0]
    name_col = cols.get('company name') or cols.get('company') or cols.get('name') or sym_col
    sector_col = cols.get('sector')
    weight_col = cols.get('weight(%)') or cols.get('weight')

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        symbol = _normalize_symbol(row.get(sym_col))
        if not symbol:
            continue
        company_name = str(row.get(name_col) or symbol)
        sector = (row.get(sector_col) if sector_col else None)
        weight = row.get(weight_col) if weight_col else None
        rows.append({
            "symbol": symbol,
            "company_name": company_name,
            "sector": sector,
            "weight": weight,
        })

    if not rows:
        return 0

    # Map stock_code from instruments.short_name using joins:
    # Priority: match by exchange_code -> scrip_id -> company_name to nifty50.symbol.
    # If no match, leave stock_code as NULL (no fallback to instruments.symbol).
    with get_conn() as conn:
        if conn is None:
            return 0
        mapped: List[Dict[str, Any]] = []
        for r in rows:
            stock_code: Optional[str] = None
            # 1) Match by exchange_code to Nifty symbol
            rec_ex = conn.execute(text(
                """
                SELECT short_name
                FROM instruments
                WHERE exchange = 'NSE' AND UPPER(exchange_code) = :sym
                LIMIT 1
                """
            ), {"sym": r["symbol"]}).fetchone()
            if rec_ex and rec_ex[0]:
                stock_code = rec_ex[0]
            # 2) Match by scrip_id to Nifty symbol
            if not stock_code:
                rec_sid = conn.execute(text(
                    """
                    SELECT short_name
                    FROM instruments
                    WHERE exchange = 'NSE' AND UPPER(scrip_id) = :sym
                    LIMIT 1
                    """
                ), {"sym": r["symbol"]}).fetchone()
                if rec_sid and rec_sid[0]:
                    stock_code = rec_sid[0]
            # 3) Match by company_name to Nifty symbol (exact, case-insensitive)
            if not stock_code:
                rec_cn = conn.execute(text(
                    """
                    SELECT short_name
                    FROM instruments
                    WHERE exchange = 'NSE' AND UPPER(company_name) = :sym
                    LIMIT 1
                    """
                ), {"sym": r["symbol"]}).fetchone()
                if rec_cn and rec_cn[0]:
                    stock_code = rec_cn[0]
            mapped.append({
                **r,
                "stock_code": stock_code,
            })

        upsert = text(
            """
            INSERT INTO nifty50_list (symbol, stock_code, company_name, exchange, weight, sector, updated_at)
            VALUES (:symbol, :stock_code, :company_name, 'NSE', :weight, :sector, NOW())
            ON CONFLICT (symbol, exchange)
            DO UPDATE SET
                stock_code = COALESCE(EXCLUDED.stock_code, nifty50_list.stock_code),
                company_name = EXCLUDED.company_name,
                weight = EXCLUDED.weight,
                sector = EXCLUDED.sector,
                updated_at = NOW()
            """
        )
        for r in mapped:
            conn.execute(upsert, r)

    logger.info("Refreshed nifty50_list: {} rows", len(rows))
    return len(rows)


def main() -> int:
    try:
        n = refresh_nifty50_list()
        print(f"nifty50_list refreshed: {n}")
        return 0
    except Exception as exc:
        logger.exception("nifty50_service failed: {}", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


