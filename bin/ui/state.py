from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionState:
    slug: str = ""
    brief_text: str = ""
    mode: str = "reuse"  # or "live"
    yt_only: bool = False
    enable_viral: bool = True
    enable_shorts: bool = True
    enable_seo: bool = True
    seed: int = 1337
    from_step: str = ""  # empty = full run



