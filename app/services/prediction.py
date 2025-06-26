"""
Mock ML prediction service with configurable delays and realistic simulation.
"""

import time
import random
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MockPredictionService:
    """
    Simulates ML model prediction with configurable processing times.
    Includes realistic error simulation and performance metrics.
    """
    
    def __init__(self, min_delay: int = 10, max_delay: int = 17):
        """
        Initialize prediction service with delay configuration.
        
        Args:
            min_delay: Minimum processing delay in seconds
            max_delay: Maximum processing delay in seconds
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.prediction_count = 0
        self.total_processing_time = 0.0
    
    def mock_model_predict(self, input_data: str) -> Dict[str, str]:
        """
        Synchronous mock prediction function as specified in requirements.
        
        Args:
            input_data: Input string for prediction
            
        Returns:
            Dictionary containing input and result
        """
        start_time = time.time()
        
        # Simulate processing delay as per requirements
        delay = random.randint(self.min_delay, self.max_delay)
        time.sleep(delay)
        
        # Generate random result
        result = str(random.randint(1000, 20000))
        
        # Track metrics
        processing_time = time.time() - start_time
        self.prediction_count += 1
        self.total_processing_time += processing_time
        
        logger.info(f"Prediction completed in {processing_time:.2f}s, result: {result}")
        
        return {"input": input_data, "result": result}
    
    async def async_model_predict(self, input_data: str) -> Dict[str, str]:
        """
        Asynchronous version of model prediction for background processing.
        
        Args:
            input_data: Input string for prediction
            
        Returns:
            Dictionary containing input and result
        """
        start_time = time.time()
        
        # Simulate async processing delay
        delay = random.randint(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
        
        # Simulate occasional processing failures (5% chance)
        if random.random() < 0.05:
            logger.warning(f"Prediction failed for input: {input_data[:50]}")
            raise Exception("Model prediction failed due to internal error")
        
        # Generate random result
        result = str(random.randint(1000, 20000))
        
        # Track metrics
        processing_time = time.time() - start_time
        self.prediction_count += 1
        self.total_processing_time += processing_time
        
        logger.info(f"Async prediction completed in {processing_time:.2f}s, result: {result}")
        
        return {"input": input_data, "result": result}
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Get performance statistics for monitoring.
        
        Returns:
            Dictionary with performance metrics
        """
        avg_time = self.total_processing_time / max(1, self.prediction_count)
        return {
            "total_predictions": self.prediction_count,
            "average_processing_time": avg_time,
            "total_processing_time": self.total_processing_time
        }


# Global service instance
prediction_service = MockPredictionService()