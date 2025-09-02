from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal

Status = Literal["PASS", "WARN", "FAIL"]


@dataclass
class GateResult:
    gate: str
    status: Status
    metrics: Dict[str, Any]
    thresholds: Dict[str, Any]
    notes: List[str]


def pass_fail(condition: bool, warn: bool = False) -> Status:
    """Convert boolean condition to PASS/WARN/FAIL status."""
    if condition:
        return "PASS"
    return "WARN" if warn else "FAIL"
