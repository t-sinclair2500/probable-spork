import logging
import os
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class OperatorConfig:
    """Configuration manager for operator console"""

    def __init__(self, config_path: str = "conf/operator.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from operator.yaml"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    logger.info(
                        f"[config] Loaded operator config from {self.config_path}"
                    )
                    return config
            else:
                logger.warning(
                    f"[config] Operator config not found at {self.config_path}, using defaults"
                )
                return self._get_default_config()
        except Exception as e:
            logger.error(
                f"[config] Failed to load operator config: {e}, using defaults"
            )
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "server": {
                "host": "127.0.0.1",
                "port": 8008,
                "workers": 1,
                "log_level": "info",
                "allow_external_bind": False,
            },
            "ui": {
                "enabled": True,
                "host": "localhost",
                "port": 7860,
                "share": False,
                "debug": False,
                "features": {
                    "real_time_updates": True,
                    "sse_enabled": True,
                    "polling_fallback": True,
                    "download_artifacts": True,
                    "job_cancellation": True,
                },
            },
            "security": {
                "admin_token_env": "ADMIN_TOKEN",
                "default_token": "default-admin-token-change-me",
                "rate_limiting": {
                    "enabled": True,
                    "job_creation_per_minute": 5,
                    "api_requests_per_minute": 60,
                    "burst_size": 10,
                },
                "cors": {
                    "enabled": False,
                    "allow_origins": [],
                    "allow_credentials": False,
                    "allow_methods": [],
                    "allow_headers": [],
                    "expose_headers": [],
                    "max_age": 86400,
                },
                "security_headers": {
                    "enabled": True,
                    "hsts_seconds": 31536000,
                    "content_security_policy": "default-src 'self'",
                    "x_content_type_options": "nosniff",
                    "x_frame_options": "DENY",
                    "x_xss_protection": "1; mode=block",
                },
            },
            "gates": {
                "script": {
                    "required": True,
                    "auto_approve": False,
                    "timeout_minutes": 60,
                },
                "storyboard": {
                    "required": True,
                    "auto_approve": False,
                    "timeout_minutes": 120,
                },
                "assets": {
                    "required": True,
                    "auto_approve": False,
                    "timeout_minutes": 180,
                },
                "audio": {
                    "required": True,
                    "auto_approve": False,
                    "timeout_minutes": 60,
                },
                "outline": {
                    "required": False,
                    "auto_approve": True,
                    "timeout_minutes": 30,
                },
                "research": {
                    "required": False,
                    "auto_approve": True,
                    "timeout_minutes": 45,
                },
                "animatics": {
                    "required": False,
                    "auto_approve": True,
                    "timeout_minutes": 90,
                },
                "assemble": {
                    "required": False,
                    "auto_approve": True,
                    "timeout_minutes": 120,
                },
                "acceptance": {
                    "required": False,
                    "auto_approve": True,
                    "timeout_minutes": 30,
                },
            },
            "storage": {
                "db_path": "jobs.db",
                "runs_dir": "runs",
                "artifacts_dir": "artifacts",
                "events_retention_days": 30,
                "max_events_per_job": 1000,
            },
            "pipeline": {
                "max_concurrent_jobs": 1,
                "job_timeout_hours": 24,
                "stage_timeouts": {
                    "outline": 30,
                    "research": 45,
                    "script": 60,
                    "storyboard": 120,
                    "assets": 180,
                    "animatics": 90,
                    "audio": 60,
                    "assemble": 120,
                    "acceptance": 30,
                },
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key path (e.g., 'server.port')"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def reload(self):
        """Reload configuration from file"""
        self.config = self._load_config()
        logger.info("[config] Operator config reloaded")

    def get_sanitized_config(self) -> Dict[str, Any]:
        """Get configuration without sensitive information"""
        config_copy = self.config.copy()

        # Redact sensitive information
        if "security" in config_copy:
            security = config_copy["security"]
            if "default_token" in security:
                security["default_token"] = "[REDACTED]"
            if "admin_token_env" in security:
                security["admin_token_env"] = "[REDACTED]"

        return config_copy

    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration and return validation results"""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "recommendations": [],
        }

        try:
            # Check server configuration
            host = self.get("server.host", "127.0.0.1")
            allow_external = self.get("server.allow_external_bind", False)

            if not allow_external and host not in ["127.0.0.1", "localhost", "::1"]:
                validation_results["errors"].append(
                    f"External binding not allowed but host is {host}"
                )
                validation_results["valid"] = False

            # Check security configuration
            if (
                not self.get("security.admin_token_env")
                and self.get("security.default_token")
                == "default-admin-token-change-me"
            ):
                validation_results["warnings"].append(
                    "Using default admin token - change this in production"
                )

            # Check UI configuration
            ui_enabled = self.get("ui.enabled", True)
            if ui_enabled:
                ui_port = self.get("ui.port", 7860)
                if ui_port < 1024 or ui_port > 65535:
                    validation_results["errors"].append(f"Invalid UI port: {ui_port}")
                    validation_results["valid"] = False

            # Check storage paths
            runs_dir = self.get("storage.runs_dir", "runs")
            if not os.path.exists(runs_dir):
                validation_results["warnings"].append(
                    f"Runs directory does not exist: {runs_dir}"
                )
                validation_results["recommendations"].append(
                    f"Create directory: mkdir -p {runs_dir}"
                )

            # Check database path
            db_path = self.get("storage.db_path", "jobs.db")
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                validation_results["warnings"].append(
                    f"Database directory does not exist: {db_dir}"
                )
                validation_results["recommendations"].append(
                    f"Create directory: mkdir -p {db_dir}"
                )

        except Exception as e:
            validation_results["errors"].append(f"Configuration validation failed: {e}")
            validation_results["valid"] = False

        return validation_results


# Global config instance
operator_config = OperatorConfig()
