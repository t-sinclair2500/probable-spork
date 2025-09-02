# bin/config/pipeline.py
from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, Field

StepStatus = Literal["OK", "FAIL", "PARTIAL", "SKIP", "TIMEOUT"]


class StepPolicy(BaseModel):
    required: bool = True
    on_fail: Literal["block", "warn", "skip"] = (
        "block"  # only relevant if required=False
    )

    class Config:
        extra = "allow"


class PipelineConfig(BaseModel):
    steps: Dict[str, StepPolicy] = Field(default_factory=dict)

    class Config:
        extra = "allow"
