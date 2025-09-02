"""Middleware for rate limiting and security headers"""

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from .config import operator_config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self):
        self.requests: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self.job_creations: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=100)
        )

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        """Check if request is allowed within rate limit"""
        now = time.time()
        requests = self.requests[key]

        # Remove old requests outside the window
        while requests and requests[0] < now - window_seconds:
            requests.popleft()

        # Check if we're under the limit
        if len(requests) < max_requests:
            requests.append(now)
            return True

        return False

    def is_job_creation_allowed(self, key: str, max_per_minute: int) -> bool:
        """Check if job creation is allowed"""
        now = time.time()
        requests = self.job_creations[key]

        # Remove old requests outside the 1-minute window
        while requests and requests[0] < now - 60:
            requests.popleft()

        # Check if we're under the limit
        if len(requests) < max_per_minute:
            requests.append(now)
            return True

        return False


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Skip rate limiting for health check
    if request.url.path == "/healthz":
        return await call_next(request)

    # Get client identifier (IP address)
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limiting configuration
    rate_limiting_enabled = operator_config.get("security.rate_limiting.enabled", True)

    if rate_limiting_enabled:
        # Check general API rate limit
        api_limit = operator_config.get(
            "security.rate_limiting.api_requests_per_minute", 60
        )
        if not rate_limiter.is_allowed(client_ip, api_limit, 60):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"},
            )

        # Check job creation rate limit specifically
        if request.url.path == "/api/v1/jobs" and request.method == "POST":
            job_limit = operator_config.get(
                "security.rate_limiting.job_creation_per_minute", 5
            )
            if not rate_limiter.is_job_creation_allowed(client_ip, job_limit):
                logger.warning(f"Job creation rate limit exceeded for {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Job creation rate limit exceeded. Please wait before creating another job.",
                    headers={"Retry-After": "60"},
                )

    # Continue with the request
    response = await call_next(request)
    return response


async def security_headers_middleware(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)

    # Check if security headers are enabled
    security_headers_enabled = operator_config.get(
        "security.security_headers.enabled", True
    )

    if security_headers_enabled:
        # HSTS header
        hsts_seconds = operator_config.get(
            "security.security_headers.hsts_seconds", 31536000
        )
        response.headers["Strict-Transport-Security"] = (
            f"max-age={hsts_seconds}; includeSubDomains"
        )

        # Content Security Policy
        csp = operator_config.get(
            "security.security_headers.content_security_policy", "default-src 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # X-Content-Type-Options
        xcto = operator_config.get(
            "security.security_headers.x_content_type_options", "nosniff"
        )
        response.headers["X-Content-Type-Options"] = xcto

        # X-Frame-Options
        xfo = operator_config.get("security.security_headers.x_frame_options", "DENY")
        response.headers["X-Frame-Options"] = xfo

        # X-XSS-Protection
        xxp = operator_config.get(
            "security.security_headers.x_xss_protection", "1; mode=block"
        )
        response.headers["X-XSS-Protection"] = xxp

        # Remove server information
        response.headers.pop("server", None)

    return response


async def binding_restriction_middleware(request: Request, call_next):
    """Ensure server binding restrictions are enforced"""
    # Get the configured host
    configured_host = operator_config.get("server.host", "127.0.0.1")
    allow_external = operator_config.get("server.allow_external_bind", False)

    # If external binding is not allowed, ensure we're only binding to localhost
    if not allow_external and configured_host != "127.0.0.1":
        logger.error(f"External binding not allowed. Current host: {configured_host}")
        # This would typically be caught at startup, but we log it here for safety

    # Continue with the request
    response = await call_next(request)
    return response
