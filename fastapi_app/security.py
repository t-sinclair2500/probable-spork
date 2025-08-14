import os
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
import re

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
            logger.warning("No admin token configured, using fallback")
            token = "default-admin-token-change-me"
    return token


def redact_secrets(text: str) -> str:
    """Redact sensitive information from text"""
    if not text:
        return text
    
    # Redact tokens (Bearer tokens, API keys, etc.)
    text = re.sub(r'Bearer\s+[a-zA-Z0-9\-._~+/]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'[a-zA-Z0-9\-._~+/]{20,}', '[REDACTED]', text)
    
    # Redact common secret patterns
    text = re.sub(r'password["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'password: [REDACTED]', text)
    text = re.sub(r'api_key["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'api_key: [REDACTED]', text)
    text = re.sub(r'token["\']?\s*[:=]\s*["\']?[^"\s]+["\']?', 'token: [REDACTED]', text)
    
    return text


async def get_current_operator(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Validate Bearer token and return operator identifier"""
    admin_token = get_admin_token()
    
    if credentials.credentials != admin_token:
        # Log only first 8 characters for debugging, redact the rest
        token_preview = credentials.credentials[:8] + "..." if len(credentials.credentials) > 8 else "[SHORT]"
        logger.warning(f"Invalid token attempt: {token_preview}")
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


def get_cors_config() -> dict:
    """Get CORS configuration from operator config"""
    cors_enabled = operator_config.get("security.cors.enabled", False)
    
    if not cors_enabled:
        return {
            "allow_origins": [],
            "allow_credentials": False,
            "allow_methods": [],
            "allow_headers": [],
            "expose_headers": [],
            "max_age": 86400
        }
    
    return {
        "allow_origins": operator_config.get("security.cors.allow_origins", []),
        "allow_credentials": operator_config.get("security.cors.allow_credentials", False),
        "allow_methods": operator_config.get("security.cors.allow_methods", ["GET", "POST", "PUT", "DELETE"]),
        "allow_headers": operator_config.get("security.cors.allow_headers", ["*"]),
        "expose_headers": operator_config.get("security.cors.expose_headers", []),
        "max_age": operator_config.get("security.cors.max_age", 86400)
    }


def validate_binding_config() -> bool:
    """Validate that binding configuration is secure"""
    host = operator_config.get("server.host", "127.0.0.1")
    allow_external = operator_config.get("server.allow_external_bind", False)
    
    # If external binding is not allowed, ensure we're only binding to localhost
    if not allow_external and host != "127.0.0.1":
        logger.error(f"Security violation: External binding not allowed but host is {host}")
        return False
    
    # If external binding is allowed, log a warning
    if allow_external and host == "0.0.0.0":
        logger.warning("External binding enabled - server will be accessible from any IP")
    
    return True


def get_security_summary() -> dict:
    """Get a security summary for logging (no secrets)"""
    return {
        "cors_enabled": operator_config.get("security.cors.enabled", False),
        "rate_limiting_enabled": operator_config.get("security.rate_limiting.enabled", True),
        "security_headers_enabled": operator_config.get("security.security_headers.enabled", True),
        "binding_host": operator_config.get("server.host", "127.0.0.1"),
        "allow_external_bind": operator_config.get("server.allow_external_bind", False),
        "admin_token_set": bool(os.getenv("ADMIN_TOKEN")),
        "default_token_used": not bool(os.getenv("ADMIN_TOKEN"))
    }
