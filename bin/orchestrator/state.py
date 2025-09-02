from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from bin.utils.logs import audit_event, get_logger

log = get_logger("state")


@dataclass
class Step:
    name: str
    cmd: List[str]
    required: bool = True
    on_fail: str = "block"  # 'block'|'warn'|'skip'
    idempotent_outputs: Optional[List[str]] = None  # file paths to check before running


class StateMachine:
    """
    Minimal sequential state machine. The runner callable executes a step and
    returns one of: "OK", "FAIL", "PARTIAL", or "SKIP".
    """

    def __init__(self, steps: List[Step], runner: Callable[[str, List[str]], str]):
        self.steps = steps
        self.runner = runner

    def already_satisfied(self, step: Step) -> bool:
        if not step.idempotent_outputs:
            return False
        import os

        return all(os.path.exists(p) for p in step.idempotent_outputs)

    def run(self, force: bool = False) -> str:
        final_status = "OK"
        for s in self.steps:
            if not force and self.already_satisfied(s):
                audit_event(s.name, "SKIP", notes="outputs_present")
                log.info(f"[{s.name}] SKIP (idempotent outputs present)")
                if final_status == "OK":
                    final_status = "PARTIAL"  # SKIP counts as partial
                continue

            status = self.runner(s.name, s.cmd)
            if status == "OK":
                continue

            if status == "FAIL":
                # Enforce policy based on required/optional + on_fail
                if s.required or s.on_fail == "block":
                    audit_event(s.name, "FAIL", notes="policy_block")
                    log.error(f"[{s.name}] FAIL (policy block)")
                    return "FAIL"
                if s.on_fail == "skip":
                    audit_event(s.name, "SKIP", notes="policy_skip")
                    log.warning(f"[{s.name}] SKIP (optional failure)")
                    if final_status == "OK":
                        final_status = "PARTIAL"
                    continue
                # warn
                audit_event(s.name, "PARTIAL", notes="policy_warn")
                log.warning(f"[{s.name}] PARTIAL (optional failure; continuing)")
                if final_status == "OK":
                    final_status = "PARTIAL"
                continue

            if status in ("PARTIAL", "SKIP") and final_status == "OK":
                final_status = "PARTIAL"
        return final_status
