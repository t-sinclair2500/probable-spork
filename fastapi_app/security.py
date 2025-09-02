import logging
import os
import re
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import operator_config

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


def get_admin_token() -> str:
    """Get admin token from environment or config"""
    # First try environment variable
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        # Fall back to config default
        token = operator_config.get("security.default_token")
        if not token:
            logger.warning("[security] No admin token configured, using fallback")
            token = "default-admin-token-change-me"
    return token


def redact_secrets(text: str) -> str:
    """Redact sensitive information from text"""
    if not text:
        return text

    # Redact tokens (Bearer tokens, API keys, etc.)
    text = re.sub(r"Bearer\s+[a-zA-Z0-9\-._~+/]+", "Bearer [REDACTED]", text)
    text = re.sub(r"[a-zA-Z0-9\-._~+/]{20,}", "[REDACTED]", text)

    # Redact common secret patterns
    text = re.sub(
        r'password["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', "password: [REDACTED]", text
    )
    text = re.sub(
        r'api_key["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', "api_key: [REDACTED]", text
    )
    text = re.sub(
        r'token["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', "token: [REDACTED]", text
    )

    return text


async def get_current_operator(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate Bearer token and return operator identifier"""
    admin_token = get_admin_token()

    if credentials.credentials != admin_token:
        # Log only first 8 characters for debugging, redact the rest
        token_preview = (
            credentials.credentials[:8] + "..."
            if len(credentials.credentials) > 8
            else "[SHORT]"
        )
        logger.warning(f"[security] Invalid token attempt: {token_preview}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # For now, return a default operator name
    # TODO: Implement proper operator management
    return "admin"


def is_authenticated(token: str) -> bool:
    """Check if a token is valid"""
    admin_token = get_admin_token()
    return token == admin_token


def get_cors_config() -> Dict[str, Any]:
    """Get CORS configuration with secure defaults"""
    cors_enabled = operator_config.get("security.cors.enabled", False)

    if not cors_enabled:
        logger.info("[security] CORS disabled - no cross-origin requests allowed")
        return {
            "allow_origins": [],
            "allow_credentials": False,
            "allow_methods": [],
            "allow_headers": [],
            "expose_headers": [],
            "max_age": 86400,
        }

    # Get UI port from config
    ui_port = operator_config.get("ui.port", 7860)
    ui_host = operator_config.get("ui.host", "localhost")

    # Build allowed origins for UI
    allowed_origins = [
        f"http://{ui_host}:{ui_port}",
        f"http://127.0.0.1:{ui_port}",
        f"http://localhost:{ui_port}",
    ]

    # Add any explicitly configured origins
    config_origins = operator_config.get("security.cors.allow_origins", [])
    if config_origins:
        allowed_origins.extend(config_origins)

    logger.info(f"[security] CORS enabled for origins: {allowed_origins}")

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": operator_config.get(
            "security.cors.allow_credentials", False
        ),
        "allow_methods": operator_config.get(
            "security.cors.allow_methods", ["GET", "POST", "PUT", "DELETE"]
        ),
        "allow_headers": operator_config.get("security.cors.allow_headers", ["*"]),
        "expose_headers": operator_config.get("security.cors.expose_headers", []),
        "max_age": operator_config.get("security.cors.max_age", 86400),
    }


def validate_binding_config() -> bool:
    """Validate that binding configuration is secure by default"""
    host = operator_config.get("server.host", "127.0.0.1")
    allow_external = operator_config.get("server.allow_external_bind", False)

    # Security check: if external binding is not explicitly allowed, enforce localhost
    if not allow_external:
        if host not in ["127.0.0.1", "localhost", "::1"]:
            logger.error(
                f"[security] Security violation: External binding not allowed but host is {host}"
            )
            logger.error("[security] Forcing binding to 127.0.0.1 for security")
            # Override the config to be secure
            operator_config.config["server"]["host"] = "127.0.0.1"
            return False

    # If external binding is allowed, log a warning
    if allow_external and host in ["0.0.0.0", "::"]:
        logger.warning(
            "[security] External binding enabled - server will be accessible from any IP"
        )
        logger.warning("[security] This is not recommended for production use")

    logger.info(
        f"[security] Server binding validated: {host} (external: {allow_external})"
    )
    return True


def enforce_local_binding() -> str:
    """Enforce local-only binding for security"""
    host = operator_config.get("server.host", "127.0.0.1")
    allow_external = operator_config.get("server.allow_external_bind", False)

    if not allow_external:
        # Force localhost binding
        safe_host = "127.0.0.1"
        if host != safe_host:
            logger.warning(
                f"[security] Forcing local binding from {host} to {safe_host}"
            )
            operator_config.config["server"]["host"] = safe_host
        return safe_host

    return host


def get_security_summary() -> Dict[str, Any]:
    """Get a security summary for logging (no secrets)"""
    return {
        "cors_enabled": operator_config.get("security.cors.enabled", False),
        "rate_limiting_enabled": operator_config.get(
            "security.rate_limiting.enabled", True
        ),
        "security_headers_enabled": operator_config.get(
            "security.security_headers.enabled", True
        ),
        "binding_host": operator_config.get("server.host", "127.0.0.1"),
        "allow_external_bind": operator_config.get("server.allow_external_bind", False),
        "admin_token_set": bool(os.getenv("ADMIN_TOKEN")),
        "default_token_used": not bool(os.getenv("ADMIN_TOKEN")),
        "local_binding_enforced": not operator_config.get(
            "server.allow_external_bind", False
        ),
    }


def log_security_status():
    """Log current security configuration status"""
    summary = get_security_summary()

    logger.info("[security] Security configuration:")
    logger.info(
        f"[security]   Local binding enforced: {summary['local_binding_enforced']}"
    )
    logger.info(f"[security]   Binding host: {summary['binding_host']}")
    logger.info(f"[security]   CORS enabled: {summary['cors_enabled']}")
    logger.info(f"[security]   Rate limiting: {summary['rate_limiting_enabled']}")
    logger.info(f"[security]   Security headers: {summary['security_headers_enabled']}")
    logger.info(
        f"[security]   Admin token: {'Set' if summary['admin_token_set'] else 'Using default'}"
    )

    if not summary["local_binding_enforced"]:
        logger.warning(
            "[security] WARNING: External binding is enabled - server accessible from any IP"
        )

    if not summary["admin_token_set"]:
        logger.warning(
            "[security] WARNING: Using default admin token - change this in production"
        )
