import os
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

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


async def get_current_operator(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Validate Bearer token and return operator identifier"""
    admin_token = get_admin_token()
    
    if credentials.credentials != admin_token:
        logger.warning(f"Invalid token attempt: {credentials.credentials[:8]}...")
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
            "allow_headers": []
        }
    
    return {
        "allow_origins": operator_config.get("security.cors.allow_origins", []),
        "allow_credentials": operator_config.get("security.cors.allow_credentials", False),
        "allow_methods": operator_config.get("security.cors.allow_methods", []),
        "allow_headers": operator_config.get("security.cors.allow_headers", [])
    }
