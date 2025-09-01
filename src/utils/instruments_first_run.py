from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from loguru import logger
from sqlalchemy import text

from .postgres import get_engine, ensure_tables
from .security_master import download_and_extract_security_master
from .security_master_loader import load_and_normalize


def _table_exists() -> bool:
    engine = get_engine()
    if engine is None:
        return False
    with engine.connect() as conn:
        res = conn.execute(text(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = current_schema()
                  AND table_name = 'instruments'
            )
            """
        ))
        row = res.fetchone()
        return bool(row[0]) if row else False


def _row_count() -> int:
    engine = get_engine()
    if engine is None:
        return 0
    with engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM instruments"))
        row = res.fetchone()
        return int(row[0]) if row else 0


def _ensure_security_master_available(root_dir: Path) -> None:
    root_dir.mkdir(parents=True, exist_ok=True)
    required = [root_dir / "NSEScripMaster.txt", root_dir / "BSEScripMaster.txt"]
    if all(p.exists() for p in required):
        return
    logger.info("SecurityMaster files missing; downloading to {}", root_dir)
    download_and_extract_security_master(destination_dir=root_dir)


def populate_instruments_from_security_master(root_dir: Path) -> int:
    """Load SecurityMaster files and upsert rows into instruments.

    Returns number of rows written.
    """
    engine = get_engine()
    if engine is None:
        logger.warning("No database engine configured; skipping instruments population")
        return 0

    _ensure_security_master_available(root_dir)
    frames = load_and_normalize(root_dir)
    combined = frames["NSE"].copy()
    combined = combined._append(frames["BSE"], ignore_index=True)

    # Basic sanitation: drop empty/zero tokens, cast lot_size to string, de-dup by token
    combined["token"] = combined["token"].astype(str).str.strip()
    combined = combined[(combined["token"] != "") & (combined["token"] != "0")].copy()
    combined["lot_size"] = combined["lot_size"].astype(str)
    combined = combined.drop_duplicates(subset=["token"], keep="first").reset_index(drop=True)

    # Retain raw source row: reload original CSV rows keyed by token for each exchange
    # Build maps for raw NSE and raw BSE to attach into JSONB
    from .security_master_loader import load_nse, load_bse, NSE_FILE, BSE_FILE
    import pandas as pd
    nse_df, _ = load_nse(root_dir / NSE_FILE)
    bse_df, _ = load_bse(root_dir / BSE_FILE)
    nse_raw_by_token = {str(r["Token"]).strip(): {k: (None if pd.isna(v) else v) for k, v in r.items()} for _, r in nse_df.iterrows()}
    bse_raw_by_token = {str(r["ScripCode"]).strip(): {k: (None if pd.isna(v) else v) for k, v in r.items()} for _, r in bse_df.iterrows()}

    def attach_raw(row: dict) -> dict:
        tok = row.get("token")
        exch = row.get("exchange")
        raw = None
        if exch == "NSE":
            raw = nse_raw_by_token.get(str(tok))
        elif exch == "BSE":
            raw = bse_raw_by_token.get(str(tok))
        row["raw"] = raw
        return row

    rows = [attach_raw(r) for r in combined.to_dict(orient="records")]
    if not rows:
        logger.info("No instrument rows to write")
        return 0

    # Use a cursor with %s placeholders for compatibility with psycopg driver
    upsert_sql = (
        "INSERT INTO instruments (token, symbol, short_name, company_name, series, isin, lot_size, exchange, last_update, raw) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) "
        "ON CONFLICT (token) DO UPDATE SET "
        "symbol = EXCLUDED.symbol, "
        "short_name = EXCLUDED.short_name, "
        "company_name = EXCLUDED.company_name, "
        "series = EXCLUDED.series, "
        "isin = EXCLUDED.isin, "
        "lot_size = EXCLUDED.lot_size, "
        "exchange = EXCLUDED.exchange, "
        "raw = EXCLUDED.raw, "
        "last_update = NOW()"
    )

    # Chunk inserts to avoid very large transactions
    batch_size = 2000
    total_written = 0
    with engine.begin() as conn:
        raw_conn = conn.connection
        with raw_conn.cursor() as cur:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                import json
                params = [
                    (
                        r.get("token"),
                        r.get("symbol"),
                        r.get("short_name"),
                        r.get("company_name"),
                        r.get("series"),
                        r.get("isin"),
                        r.get("lot_size"),
                        r.get("exchange"),
                        json.dumps(r.get("raw")) if r.get("raw") is not None else None,
                    )
                    for r in batch
                ]
                cur.executemany(upsert_sql, params)
                total_written += len(params)

    logger.info("Upserted {} instrument rows", total_written)
    return total_written


def ensure_instruments_first_run(root_dir: Optional[Path] = None) -> None:
    """Ensure instruments table exists and is populated on first run."""
    engine = get_engine()
    if engine is None:
        logger.debug("No database configured; skipping instruments first-run init")
        return

    ensure_tables()

    if not _table_exists():
        logger.info("Created instruments table")

    try:
        count = _row_count()
    except Exception:
        # If instruments table not yet visible, try again after ensure_tables
        ensure_tables()
        count = _row_count()

    if count > 0:
        logger.info("Instruments already populated ({} rows)", count)
        return

    root = (root_dir or (Path.cwd() / "SecurityMaster")).resolve()
    written = populate_instruments_from_security_master(root)
    logger.info("Instruments first-run population completed: {} rows", written)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ensure instruments table exists and populate on first run")
    parser.add_argument("--root", type=str, default=str(Path.cwd() / "SecurityMaster"), help="Directory of SecurityMaster files")
    args = parser.parse_args(argv)

    try:
        ensure_instruments_first_run(Path(args.root))
        return 0
    except Exception as exc:
        logger.exception("Failed instruments first-run: {}", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


