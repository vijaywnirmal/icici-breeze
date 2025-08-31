from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set, Dict

import requests
from bs4 import BeautifulSoup

from ..utils.response import log_exception
from ..utils.config import settings
from ..utils.postgres import get_conn, ensure_tables as ensure_pg_tables
from sqlalchemy import text


HOLIDAYS_TABLE = "market_holidays"


def ensure_tables() -> None:
	"""Ensure PostgreSQL tables exist for holidays."""
	try:
		ensure_pg_tables()
	except Exception:
		pass


def list_holidays() -> Set[str]:
	"""Return known holidays from PostgreSQL plus static env ones (dates only)."""
	dates: Set[str] = set(settings.market_holidays or set())
	try:
		with get_conn() as conn:
			if conn is None:
				return dates
			res = conn.execute(text(f"SELECT date FROM {HOLIDAYS_TABLE}"))
			for row in res:
				d = (row[0] or "").strip()
				if d:
					dates.add(d)
	except Exception as exc:
		log_exception(exc, context="holidays.list_holidays.select")
	return dates


def list_holiday_objects() -> List[Dict[str, str]]:
	"""Return list of {date, name} from DB, ordered by date."""
	items: List[Dict[str, str]] = []
	try:
		with get_conn() as conn:
			if conn is None:
				return items
			res = conn.execute(text(f"SELECT date, name FROM {HOLIDAYS_TABLE} ORDER BY date"))
			for date_val, name_val in res:
				if date_val:
					items.append({"date": str(date_val), "name": (name_val or "").strip()})
	except Exception as exc:
		log_exception(exc, context="holidays.list_holiday_objects")
	return items


def upsert_holidays(dates: List[str], source: str = "nse") -> int:
	"""Upsert given list of YYYY-MM-DD dates into PostgreSQL table.

	Returns number of rows attempted.
	"""
	to_insert: List[str] = []
	seen = set()
	for d in dates:
		if not d or d in seen:
			continue
		seen.add(d)
		to_insert.append(d)
	if not to_insert:
		return 0
	try:
		ensure_tables()
		with get_conn() as conn:
			if conn is None:
				return 0
			for d in to_insert:
				conn.execute(
					text(
						f"""
						INSERT INTO {HOLIDAYS_TABLE} (date, source, updated_at)
						VALUES (:date, :source, :updated_at)
						ON CONFLICT (date)
						DO UPDATE SET source = EXCLUDED.source, updated_at = EXCLUDED.updated_at
						"""
					),
					{
						"date": d,
						"source": source,
						"updated_at": datetime.utcnow().isoformat() + "Z",
					},
				)
		return len(to_insert)
	except Exception as exc:
		log_exception(exc, context="holidays.upsert_holidays")
		return 0


def upsert_holidays_with_names(dates: List[str], names: List[Optional[str]], source: str = "csv") -> int:
	"""Upsert holidays with names."""
	if not dates:
		return 0
	try:
		ensure_tables()
		with get_conn() as conn:
			if conn is None:
				return 0
			for idx, d in enumerate(dates):
				if not d:
					continue
				name_val = names[idx] if idx < len(names) else None
				conn.execute(
					text(
						f"""
						INSERT INTO {HOLIDAYS_TABLE} (date, name, source, updated_at)
						VALUES (:date, :name, :source, :updated_at)
						ON CONFLICT (date)
						DO UPDATE SET name = COALESCE(EXCLUDED.name, {HOLIDAYS_TABLE}.name), source = EXCLUDED.source, updated_at = EXCLUDED.updated_at
						"""
					),
					{
						"date": d,
						"name": name_val,
						"source": source,
						"updated_at": datetime.utcnow().isoformat() + "Z",
					},
				)
		return len(dates)
	except Exception as exc:
		log_exception(exc, context="holidays.upsert_holidays_with_names")
		return 0


def scrape_nse_holidays(year: Optional[int] = None) -> List[str]:
	"""Scrape NSE holidays page and extract list of YYYY-MM-DD dates.

	Best-effort: if parsing fails, returns empty list.
	"""
	try:
		url = "https://www.nseindia.com/resources/exchange-communication-holidays"
		year = year or datetime.now().year
		req = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
		req.raise_for_status()
		soup = BeautifulSoup(req.text, "html.parser")
		# Heuristic: find all table cells that contain a date-like pattern
		candidates: List[str] = []
		for td in soup.find_all("td"):
			text = (td.get_text(strip=True) or "").replace("\n", " ")
			# Try common formats: DD-Mon-YYYY or DD/MM/YYYY or YYYY-MM-DD
			if not text:
				continue
			# Normalize a few common cases to YYYY-MM-DD if possible
			dt: Optional[str] = None
			for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
				try:
					parsed = datetime.strptime(text, fmt)
					if parsed.year == year:
						dt = parsed.date().isoformat()
						break
				except Exception:
					pass
			if dt:
				candidates.append(dt)
		# unique & sorted
		unique = sorted(set(candidates))
		return unique
	except Exception as exc:
		log_exception(exc, context="holidays.scrape_nse_holidays")
		return []


def seed_holidays_from_csv() -> int:
	"""One-time seed: load holidays from CSV into DB if table is empty.

	Returns number of rows inserted (best-effort).
	"""
	try:
		# Load from CSV and upsert (date + name if available). This will also
		# backfill names for rows that already exist.
		try:
			import csv, os
			from ..utils.holidays_csv import _normalize_date
			path = settings.holidays_csv_path
			if not path or not os.path.exists(path):
				return 0
			dates: List[str] = []
			names: List[Optional[str]] = []
			with open(path, newline="", encoding="utf-8") as fh:
				reader = csv.DictReader(fh)
				for row in reader:
					raw_date = (row.get("Date") or row.get("date") or "").strip()
					nm = (row.get("Occasion") or row.get("Occassion") or row.get("Holiday") or None)
					iso = _normalize_date(raw_date)
					if iso:
						dates.append(iso)
						names.append(nm)
		except Exception as exc:
			log_exception(exc, context="holidays.seed_holidays_from_csv.read")
			return 0
		if not dates:
			return 0
		return upsert_holidays_with_names(dates, names, source="csv")
	except Exception as exc:
		log_exception(exc, context="holidays.seed_holidays_from_csv")
		return 0


