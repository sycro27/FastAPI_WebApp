"""
Utility functions for common operations and configurations.
"""

import os
import logging
import json
from typing import Dict, Any
from datetime import datetime


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log') if os.getenv('LOG_TO_FILE') else logging.NullHandler()
        ]
    )


def get_config() -> Dict[str, Any]:
    """
    Get application configuration from environment variables.
    
    Returns:
        Configuration dictionary
    """
    return {
        "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
        "prediction_timeout": int(os.getenv("PREDICTION_TIMEOUT", "30")),
        "max_input_length": int(os.getenv("MAX_INPUT_LENGTH", "10000")),
        "result_ttl": int(os.getenv("RESULT_TTL", "86400")),
    }


def format_response_time(start_time: datetime) -> str:
    """
    Calculate and format response time.
    
    Args:
        start_time: Request start time
        
    Returns:
        Formatted response time string
    """
    duration = datetime.now() - start_time
    return f"{duration.total_seconds():.3f}s"


class HealthChecker:
    """Health check utilities for monitoring service status."""
    
    @staticmethod
    def check_redis_connection(redis_client) -> bool:
        """
        Check Redis connectivity.
        
        Args:
            redis_client: Redis client instance
            
        Returns:
            True if connected, False otherwise
        """
        try:
            redis_client.ping()
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """
        Get overall system health status.
        
        Returns:
            Health status dictionary
        """
        from app.services.queue import queue_service
        from app.services.prediction import prediction_service
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",
            "services": {
                "redis": HealthChecker.check_redis_connection(queue_service.redis_client),
                "prediction_service": True,  # Always available for mock service
            },
            "metrics": prediction_service.get_performance_metrics()
        }