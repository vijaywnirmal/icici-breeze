import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger


NSE_FILE = "NSEScripMaster.txt"
BSE_FILE = "BSEScripMaster.txt"


@dataclass
class NormalizedRow:
    exchange: str
    token: str
    symbol: str
    company_name: str
    series: str
    isin: str
    lot_size: int


def read_csv_with_auto_delimiter(path: Path) -> pd.DataFrame:
    # Files appear to be comma-separated with quoted fields
    df = pd.read_csv(
        path,
        sep=",",
        engine="python",
        quotechar='"',
        skipinitialspace=True,
        dtype=str,
    )
    return df


def _clean_str_series(series: pd.Series) -> pd.Series:
    # Normalize placeholder nulls like 'nan', 'None', 'NULL' to empty string
    return (
        series.astype(str)
        .str.strip()
        .replace({
            "nan": "",
            "NaN": "",
            "None": "",
            "NONE": "",
            "NULL": "",
        })
    )


def load_nse(path: Path) -> Tuple[pd.DataFrame, List[str]]:
    required = [
        "Token",
        # Symbol can be empty in some rows; we'll fallback to ShortName
        "CompanyName",
        "Series",
        "ISINCode",
        # Prefer BoardLotQty, fallback to Lotsize if missing/zero
        "ExchangeCode",
    ]
    df = read_csv_with_auto_delimiter(path)
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("NSE file missing required columns: {}", ", ".join(missing))
        raise ValueError(f"NSE file missing required columns: {missing}")
    return df, required


def load_bse(path: Path) -> Tuple[pd.DataFrame, List[str]]:
    required = [
        "ScripCode",
        "ShortName",
        "ScripName",
        "ScripID",
        "Series",
        "ISINCode",
        "MarketLot",
        "ExchangeCode",
    ]
    df = read_csv_with_auto_delimiter(path)
    missing = [c for c in required if c not in df.columns]
    if missing:
        logger.error("BSE file missing required columns: {}", ", ".join(missing))
        raise ValueError(f"BSE file missing required columns: {missing}")
    return df, required


def normalize_nse(df: pd.DataFrame) -> pd.DataFrame:
    # Clean candidate columns
    sym_raw = _clean_str_series(df.get("Symbol", pd.Series([""] * len(df))))
    short_raw = _clean_str_series(df.get("ShortName", pd.Series([""] * len(df))))
    comp_raw = _clean_str_series(df.get("CompanyName", pd.Series([""] * len(df))))
    series_raw = _clean_str_series(df.get("Series", pd.Series([""] * len(df))))
    isin_raw = _clean_str_series(df.get("ISINCode", pd.Series([""] * len(df))))
    exch_code = _clean_str_series(df.get("ExchangeCode", pd.Series([""] * len(df))))

    # Symbol often blank; fallback to ShortName when Symbol missing/empty
    symbol_series = sym_raw
    symbol_series = symbol_series.mask(symbol_series.eq(""), short_raw)

    # Lot size: prefer BoardLotQty if available and >0, else Lotsize
    lot_board = pd.to_numeric(df.get("BoardLotQty", 0), errors="coerce").fillna(0).astype(int)
    lot_size = lot_board
    if "Lotsize" in df.columns:
        lot_alt = pd.to_numeric(df["Lotsize"], errors="coerce").fillna(0).astype(int)
        lot_size = lot_board.where(lot_board.gt(0), lot_alt)

    out = pd.DataFrame(
        {
            "exchange": "NSE",
            "token": _clean_str_series(df["Token"]),
            "symbol": symbol_series,
            "short_name": short_raw,
            "company_name": comp_raw,
            "series": series_raw,
            "isin": isin_raw,
            "lot_size": lot_size,
            "exchange_code": exch_code,
            # NSE does not have ScripID/ScripName fields
            "scrip_id": "",
            "scrip_name": "",
        }
    )
    return out


def normalize_bse(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "exchange": "BSE",
            "token": _clean_str_series(df["ScripCode"]),
            # BSE symbol not requested; keep as short_name or empty
            "symbol": _clean_str_series(df.get("ShortName", pd.Series([""] * len(df)))),
            "short_name": _clean_str_series(df.get("ShortName", pd.Series([""] * len(df)))),
            "company_name": _clean_str_series(df.get("ScripName", pd.Series([""] * len(df)))),
            "series": _clean_str_series(df.get("Series", pd.Series([""] * len(df)))),
            "isin": _clean_str_series(df.get("ISINCode", pd.Series([""] * len(df)))),
            "lot_size": pd.to_numeric(df.get("MarketLot", 0), errors="coerce").fillna(0).astype(int),
            "exchange_code": _clean_str_series(df.get("ExchangeCode", pd.Series([""] * len(df)))),
            "scrip_id": _clean_str_series(df.get("ScripID", pd.Series([""] * len(df)))),
            "scrip_name": _clean_str_series(df.get("ScripName", pd.Series([""] * len(df)))),
        }
    )
    return out


def load_and_normalize(root_dir: Path) -> Dict[str, pd.DataFrame]:
    nse_path = root_dir / NSE_FILE
    bse_path = root_dir / BSE_FILE

    if not nse_path.exists():
        raise FileNotFoundError(f"Missing file: {nse_path}")
    if not bse_path.exists():
        raise FileNotFoundError(f"Missing file: {bse_path}")

    nse_df, _ = load_nse(nse_path)
    bse_df, _ = load_bse(bse_path)

    nse_norm = normalize_nse(nse_df)
    bse_norm = normalize_bse(bse_df)

    # Cross-exchange enrichment: fill missing NSE symbol/short_name using BSE ShortName
    try:
        # Build BSE lookup maps
        bse_isin_to_short = (
            bse_norm[["isin", "short_name"]]
            .dropna(subset=["isin"])
            .assign(isin=lambda d: d["isin"].astype(str).str.strip())
        )
        bse_isin_to_short = {
            isin: sn for isin, sn in bse_isin_to_short.itertuples(index=False)
            if str(isin).strip() != "" and str(sn).strip() != ""
        }

        def _norm_company(val: str) -> str:
            s = str(val or "").strip().upper()
            # collapse internal whitespace
            return " ".join([p for p in s.split() if p])

        bse_company_to_short = {
            _norm_company(r["company_name"]): r["short_name"]
            for _, r in bse_norm.iterrows()
            if str(r.get("short_name") or "").strip() != ""
        }

        # Prepare candidate fills for NSE
        isin_key = nse_norm["isin"].astype(str).str.strip()
        comp_key = nse_norm["company_name"].apply(_norm_company)
        fill_from_isin = isin_key.map(bse_isin_to_short).fillna("")
        fill_from_company = comp_key.map(bse_company_to_short).fillna("")

        # Fill short_name first if empty
        nse_short = nse_norm["short_name"].astype(str)
        nse_short = nse_short.mask(nse_short.eq("") | nse_short.eq("nan"), fill_from_isin)
        nse_short = nse_short.mask(nse_short.eq("") | nse_short.eq("nan"), fill_from_company)
        nse_norm["short_name"] = nse_short

        # Then ensure symbol present: prefer original Symbol/ShortName, else BSE ShortName
        nse_sym = nse_norm["symbol"].astype(str)
        # If symbol empty, use NSE short_name if available
        nse_sym = nse_sym.mask(nse_sym.eq("") | nse_sym.eq("nan"), nse_norm["short_name"].astype(str))
        # If still empty, try BSE fills
        nse_sym = nse_sym.mask(nse_sym.eq("") | nse_sym.eq("nan"), fill_from_isin)
        nse_sym = nse_sym.mask(nse_sym.eq("") | nse_sym.eq("nan"), fill_from_company)
        nse_norm["symbol"] = nse_sym
    except Exception as _exc:
        # Best-effort enrichment; proceed even if this fails
        logger.exception("NSE/BSE cross-fill failed: {}", _exc)

    # Do not filter by ExchangeCode: per ICICI files, this column isn't a plain 'NSE'/'BSE' marker

    return {"NSE": nse_norm, "BSE": bse_norm}


def preview(df: pd.DataFrame, name: str, limit: int = 5) -> None:
    logger.info("{}: rows={}, cols={}", name, len(df), list(df.columns))
    if len(df) > 0:
        logger.info("{} sample:\n{}", name, df.head(limit).to_string(index=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load and preview SecurityMaster NSE/BSE")
    parser.add_argument("--root", type=str, default=str(Path.cwd() / "SecurityMaster"), help="Directory containing SecurityMaster .txt files")
    parser.add_argument("--limit", type=int, default=5, help="Number of rows to preview")
    args = parser.parse_args(argv)

    root_dir = Path(args.root).expanduser().resolve()
    try:
        frames = load_and_normalize(root_dir)
        preview(frames["NSE"], "NSE", args.limit)
        preview(frames["BSE"], "BSE", args.limit)
        return 0
    except Exception as e:
        logger.exception("Failed to load SecurityMaster: {}", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


