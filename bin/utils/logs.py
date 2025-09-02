# bin/utils/logs.py
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

from pathlib import Path

_LOGGER_INITIALIZED = False


def _ensure_dirs() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)
    Path("logs/subprocess").mkdir(parents=True, exist_ok=True)
    Path("jobs").mkdir(parents=True, exist_ok=True)


def get_logger(name: str = "pipeline") -> logging.Logger:
    global _LOGGER_INITIALIZED
    _ensure_dirs()
    logger = logging.getLogger(name)
    if _LOGGER_INITIALIZED:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.propagate = False
    _LOGGER_INITIALIZED = True
    return logger


def _json_default(o: Any) -> Any:
    try:
        return str(o)
    except Exception:
        return None


def audit_event(step: str, status: str, **fields: Any) -> None:
    """
    Append a structured JSON line to jobs/state.jsonl with ts, step, status, and extra fields.
    """
    _ensure_dirs()
    record: Dict[str, Any] = {
        "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "step": step,
        "status": status,
    }
    if fields:
        record.update(fields)
    line = json.dumps(record, default=_json_default)
    with open("jobs/state.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
