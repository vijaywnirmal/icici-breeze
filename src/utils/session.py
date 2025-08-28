from __future__ import annotations

from typing import Optional

from ..services.breeze_service import BreezeService


_BREEZE: Optional[BreezeService] = None


def set_breeze(service: BreezeService) -> None:
	global _BREEZE
	_BREEZE = service


def get_breeze() -> Optional[BreezeService]:
	return _BREEZE


