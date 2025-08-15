from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from contextlib import asynccontextmanager

from .routes import router
from .db import db
from .config import operator_config
from .security import get_cors_config, validate_binding_config, enforce_local_binding, get_security_summary, log_security_status
from .orchestrator import orchestrator

# Configure logging
logging.basicConfig(
    level=getattr(logging, operator_config.get("server.log_level", "INFO").upper()),
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

logger = logging.getLogger(__name__)

# Background task for checking gate timeouts
async def check_gate_timeouts_task():
    """Background task to check for gate timeouts"""
    while True:
        try:
            await orchestrator.check_gate_timeouts()
            # Check every 30 seconds
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"[orchestrator] Error in gate timeout checker: {e}")
            await asyncio.sleep(60)  # Wait longer on error

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("[api] Starting Probable Spork Orchestrator")
    
    # Enforce local binding for security
    safe_host = enforce_local_binding()
    logger.info(f"[api] Enforced binding to {safe_host} for security")
    
    # Validate security configuration
    if not validate_binding_config():
        logger.error("[api] Security configuration validation failed")
        raise RuntimeError("Security configuration validation failed")
    
    # Log security summary
    log_security_status()
    
    logger.info(f"[api] Server configured for {safe_host}:{operator_config.get('server.port')}")
    
    # Start background task
    timeout_task = asyncio.create_task(check_gate_timeouts_task())
    
    yield
    
    # Shutdown
    logger.info("[api] Shutting down Probable Spork Orchestrator")
    timeout_task.cancel()
    try:
        await timeout_task
    except asyncio.CancelledError:
        pass

# Create FastAPI app
app = FastAPI(
    title="Probable Spork Orchestrator",
    description="FastAPI orchestrator for video pipeline with HITL gates",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware (configurable via operator.yaml)
cors_config = get_cors_config()
if cors_config["allow_origins"] or cors_config["allow_methods"] or cors_config["allow_headers"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
        expose_headers=cors_config["expose_headers"],
        max_age=cors_config["max_age"]
    )
    logger.info("[api] CORS enabled with configuration")
else:
    logger.info("[api] CORS disabled (default security)")

# Include routes
app.include_router(router, prefix="/api/v1")

# Add health endpoint at root level (no authentication required)
@app.get("/healthz")
async def health_check():
    """Health check endpoint (no authentication required)"""
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}
