"""
FastAPI application's entry point
"""

import logging
import uvicorn
import time
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routes.predict import router as predict_router
from app.utils.helpers import setup_logging, get_config, HealthChecker
from app.services.queue import get_queue_service

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load configuration
config = get_config()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and response times."""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url.path}")
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            logger.info(
                f"Response: {response.status_code} - "
                f"Processing time: {process_time:.3f}s"
            )
            response.headers["X-Process-Time"] = str(process_time)
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request failed after {process_time:.3f}s: {str(e)}")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown logic."""
    logger.info("Starting ZypherAI ML Prediction Platform")
    
    # Log environment variables for debugging
    logger.info(f"REDIS_URL: {os.getenv('REDIS_URL', 'Not set')}")
    logger.info(f"LOG_LEVEL: {os.getenv('LOG_LEVEL', 'Not set')}")
    logger.info(f"CORS_ORIGINS: {os.getenv('CORS_ORIGINS', 'Not set')}")

    # Initialize Redis connection with retry logic
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to Redis (attempt {attempt + 1}/{max_retries})")
            queue_service = get_queue_service()
            
            # Test the connection
            if queue_service.health_check():
                queue_service.setup_consumer_group()
                logger.info("Redis connection established and consumer group ready")
                break
            else:
                raise Exception("Redis health check failed")
                
        except Exception as e:
            logger.error(f"Failed to connect to Redis (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                import asyncio
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error("Failed to connect to Redis after all retries. Application may not function properly.")
                # Don't raise the exception - let the app start anyway for debugging

    yield

    logger.info("Shutting down ZypherAI ML Prediction Platform")


# Initialize FastAPI application
app = FastAPI(
    title="ZypherAI ML Prediction Platform",
    description="""
    A high-performance, scalable web application for machine learning model deployment and inference.
    
    ## Features
    
    * **Synchronous Predictions**: Get immediate results for ML model inference
    * **Asynchronous Processing**: Submit predictions and retrieve results later
    * **Scalable Architecture**: Redis-based queue system for high throughput
    * **Production Ready**: Comprehensive logging, monitoring, and error handling
    * **Type Safety**: Full type hints and Pydantic validation
    
    ## Usage
    
    ### Synchronous Prediction
    Send a POST request to `/predict` with your input data.
    
    ### Asynchronous Prediction
    Send a POST request to `/predict` with the `Async-Mode: true` header.
    Use the returned `prediction_id` to retrieve results from `/predict/{prediction_id}`.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Get CORS origins from environment
cors_origins = os.getenv('CORS_ORIGINS', '*').split(',')
if cors_origins == ['*']:
    cors_origins = ["*"]

# Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0", "*"]
)
app.add_middleware(RequestLoggingMiddleware)

# Routes
app.include_router(predict_router)


@app.get("/health", tags=["monitoring"], summary="Health Check")
async def health_check():
    """Comprehensive health check including Redis connectivity."""
    health_data = HealthChecker.get_system_health()
    
    # Add Redis health check
    try:
        queue_service = get_queue_service()
        redis_healthy = queue_service.health_check()
        health_data["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "url": os.getenv('REDIS_URL', 'redis://localhost:6379')
        }
    except Exception as e:
        health_data["redis"] = {
            "status": "error",
            "error": str(e),
            "url": os.getenv('REDIS_URL', 'redis://localhost:6379')
        }
    
    return health_data


@app.get("/metrics", tags=["monitoring"], summary="Performance Metrics")
async def get_metrics():
    from app.services.prediction import prediction_service
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction_service": prediction_service.get_performance_metrics(),
        "system": HealthChecker.get_system_health()
    }


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "ZypherAI ML Prediction Platform", 
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0"
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.utcnow().isoformat()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}
    )


# Optional: For running locally outside Docker (not recommended inside container)
# if __name__ == "__main__":
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8080, log_level=config["log_level"].lower())