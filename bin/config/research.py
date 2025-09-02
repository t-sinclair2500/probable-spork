# bin/config/research.py
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ProviderRateLimit(BaseModel):
    max_rps: Optional[float] = Field(None, description="Max requests per second")
    burst: Optional[int] = Field(None, description="Token bucket burst")
    min_interval_ms: Optional[int] = Field(
        None, description="Minimum ms between requests"
    )
    jitter_ms: Optional[int] = Field(
        None, description="Randomized jitter to spread load"
    )

    class Config:
        extra = "allow"


class ResearchPolicy(BaseModel):
    mode: Literal["reuse", "live"] = "reuse"
    allow_providers: List[str] = Field(default_factory=list)
    deny_providers: List[str] = Field(default_factory=list)
    min_citations: int = 1
    coverage_threshold: float = 0.6
    fact_guard: Literal["off", "warn", "block"] = "block"
    rate_limits: Dict[str, ProviderRateLimit] = Field(default_factory=dict)
    domain_scores: Dict[str, float] = Field(default_factory=dict)
    min_domain_score: Optional[float] = None

    class Config:
        extra = "allow"


class ResearchConfig(BaseModel):
    policy: ResearchPolicy = Field(default_factory=ResearchPolicy)

    class Config:
        extra = "allow"
