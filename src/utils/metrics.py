from __future__ import annotations

import threading
import time
from typing import Dict, Tuple, Any


_lock = threading.Lock()
_counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], int] = {}
_histograms: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Dict[str, Any]] = {}


def _labels_tuple(labels: Dict[str, str] | None) -> Tuple[Tuple[str, str], ...]:
    if not labels:
        return tuple()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def inc_counter(name: str, amount: int = 1, labels: Dict[str, str] | None = None) -> None:
    key = (name, _labels_tuple(labels))
    with _lock:
        _counters[key] = int(_counters.get(key, 0)) + int(amount)


def observe_histogram(name: str, value_ms: int, labels: Dict[str, str] | None = None) -> None:
    key = (name, _labels_tuple(labels))
    with _lock:
        h = _histograms.get(key)
        if not h:
            h = {"count": 0, "sum": 0, "min": None, "max": None}
            _histograms[key] = h
        h["count"] = int(h["count"]) + 1
        h["sum"] = int(h["sum"]) + int(value_ms)
        if h["min"] is None or value_ms < h["min"]:
            h["min"] = int(value_ms)
        if h["max"] is None or value_ms > h["max"]:
            h["max"] = int(value_ms)


def get_snapshot() -> Dict[str, Any]:
    with _lock:
        counters = {
            f"{name}|{dict(labels)}": val
            for (name, labels), val in _counters.items()
        }
        histos = {
            f"{name}|{dict(labels)}": data.copy()
            for (name, labels), data in _histograms.items()
        }
    return {"counters": counters, "histograms": histos}


