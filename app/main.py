"""
FastAPI application's entry point
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import time

from app.routes.predict import router as predict_router
from app.utils.helpers import setup_logging, get_config, HealthChecker

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load configuration
config = get_config()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and response times."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"Response: {response.status_code} - "
                f"Processing time: {process_time:.3f}s"
            )
            
            # Add processing time header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request failed after {process_time:.3f}s: {str(e)}")
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown tasks.
    """
    # Startup
    logger.info("Starting ZypherAI ML Prediction Platform")
    
    # Verify Redis connection
    from app.services.queue import queue_service
    try:
        queue_service.redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        # Continue startup but log the error
    
    yield
    
    # Shutdown
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["cors_origins"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(predict_router)


@app.get(
    "/health",
    tags=["monitoring"],
    summary="Health Check",
    description="Get application health status and metrics"
)
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        System health status and metrics
    """
    return HealthChecker.get_system_health()


@app.get(
    "/metrics",
    tags=["monitoring"],
    summary="Performance Metrics",
    description="Get detailed performance metrics"
)
async def get_metrics():
    """
    Get application performance metrics.
    
    Returns:
        Performance statistics and system metrics
    """
    from app.services.prediction import prediction_service
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "prediction_service": prediction_service.get_performance_metrics(),
        "system": HealthChecker.get_system_health()
    }


@app.get("/", include_in_schema=False)
async def root():
    """
    Root endpoint redirect to documentation.
    """
    return {"message": "ZypherAI ML Prediction Platform", "docs": "/docs"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Global HTTP exception handler for consistent error responses.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.utcnow().isoformat()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unexpected errors.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


"""if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        log_level=config["log_level"].lower(),
        reload=False
    )"""