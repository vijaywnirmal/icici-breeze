from __future__ import annotations

import csv
import os
from functools import lru_cache
from typing import Set

from .config import settings


@lru_cache(maxsize=1)
def load_holidays() -> Set[str]:
	"""Load holidays from a CSV file into a set of YYYY-MM-DD strings.

	CSV expectations (flexible): any column named like 'Date' containing
	YYYY-MM-DD, YYYY/MM/DD or DD-MM-YYYY formats will be parsed. If parsing
	fails, rows are skipped.
	"""
	path = settings.holidays_csv_path
	if not path or not os.path.exists(path):
		return set()
	dates: Set[str] = set()
	with open(path, newline="", encoding="utf-8") as fh:
		reader = csv.DictReader(fh)
		for row in reader:
			if not row:
				continue
			value = None
			# try common keys
			for key in ("Date", "date", "Holiday Date", "HOLIDAY_DATE"):
				if key in row and row[key]:
					value = row[key].strip()
					break
			if not value:
				# try first column fallback
				value = list(row.values())[0].strip() if row else None
			if not value:
				continue
			# normalize
			date_iso = _normalize_date(value)
			if date_iso:
				dates.add(date_iso)
	return dates


def _normalize_date(raw: str) -> str | None:
	from datetime import datetime
	for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y"):
		try:
			return datetime.strptime(raw, fmt).date().isoformat()
		except Exception:
			continue
	return None


