from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Shared literals
Mode = Literal["reuse", "live"]


class EncodeSettings(BaseModel):
    delivery_crf: int = Field(19, ge=0, le=51)
    pix_fmt: str = "yuv420p"

    class Config:
        extra = "allow"


class PerformanceSettings(BaseModel):
    max_concurrent_renders: int = Field(1, ge=1, le=16)
    pacing_cooldown_seconds: int = Field(30, ge=0, le=3600)
    encode: EncodeSettings = EncodeSettings()

    class Config:
        extra = "allow"


class GuardSettings(BaseModel):
    disk_free_gb_min: int = Field(5, ge=1, le=5000)
    thermal: str = "platform_aware"

    class Config:
        extra = "allow"


class GlobalConfig(BaseModel):
    performance: PerformanceSettings = PerformanceSettings()
    guards: GuardSettings = GuardSettings()
    seed: int = 1337
    run_id: Optional[str] = None

    class Config:
        extra = "allow"


class PipelineStepPolicy(BaseModel):
    required: bool = True
    on_fail: Literal["block", "warn", "skip"] = "block"

    class Config:
        extra = "allow"


class PipelineConfig(BaseModel):
    steps: Dict[str, PipelineStepPolicy] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class ResearchPolicy(BaseModel):
    mode: Mode = "reuse"
    allow_providers: List[str] = Field(default_factory=list)
    min_citations: int = Field(1, ge=0, le=10)

    class Config:
        extra = "allow"


class ResearchConfig(BaseModel):
    policy: ResearchPolicy = ResearchPolicy()

    class Config:
        extra = "allow"


class OllamaConfig(BaseModel):
    base_url: str = "http://127.0.0.1:11434"
    timeout_sec: float = Field(60, gt=0, le=600)

    class Config:
        extra = "allow"


class LLMDefaults(BaseModel):
    chat_model: str = "llama3.2:3b"
    generate_model: str = "llama3.2:3b"
    embeddings_model: Optional[str] = "nomic-embed-text"

    class Config:
        extra = "allow"


class LLMOptions(BaseModel):
    num_ctx: int = 4096
    num_predict: int = 512
    temperature: float = 0.4
    seed: int = 1337

    class Config:
        extra = "allow"


class ModelsConfig(BaseModel):
    ollama: OllamaConfig = OllamaConfig()
    defaults: LLMDefaults = LLMDefaults()
    options: LLMOptions = LLMOptions()

    class Config:
        extra = "allow"


class Bundle(BaseModel):
    global_: GlobalConfig = Field(alias="global")
    pipeline: PipelineConfig
    research: ResearchConfig
    models: ModelsConfig
    profile: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        extra = "allow"
