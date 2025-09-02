#!/usr/bin/env python3
"""
Flag utilities for pipeline configuration and CLI argument handling.
"""

from typing import Any, Dict

from bin.core import get_logger

log = get_logger("flags")


def compute_viral_flags(args: Any, cfg: Any) -> Dict[str, bool]:
    """
    Compute viral step flags based on CLI arguments and configuration.

    Args:
        args: Parsed CLI arguments
        cfg: Loaded configuration object

    Returns:
        Dictionary with viral step flags:
        - viral_on: Whether viral_lab should run
        - shorts_on: Whether shorts_lab should run
        - seo_on: Whether seo_packaging should run
    """
    # Get CLI flags (default to True if not specified)
    cli_viral = getattr(args, "enable_viral", True)
    cli_shorts = getattr(args, "enable_shorts", True)
    cli_seo = getattr(args, "enable_seo", True)

    # Get config values (default to True if not specified)
    cfg_viral = cfg.viral.enabled if hasattr(cfg, "viral") else True
    cfg_shorts = cfg.viral.shorts_enabled if hasattr(cfg, "viral") else True
    cfg_seo = cfg.viral.seo_enabled if hasattr(cfg, "viral") else True

    # Compute final flags (CLI AND config)
    viral_on = cli_viral and cfg_viral
    shorts_on = cli_shorts and cfg_shorts
    seo_on = cli_seo and cfg_seo

    log.info(
        f"Viral flags computed: viral={viral_on}, shorts={shorts_on}, seo={seo_on}"
    )
    log.debug(f"CLI flags: viral={cli_viral}, shorts={cli_shorts}, seo={cli_seo}")
    log.debug(f"Config flags: viral={cfg_viral}, shorts={cfg_shorts}, seo={cfg_seo}")

    return {"viral_on": viral_on, "shorts_on": shorts_on, "seo_on": seo_on}
