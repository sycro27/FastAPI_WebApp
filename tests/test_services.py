"""
Test suite for service layer components.
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock

from app.services.prediction import MockPredictionService
from app.services.queue import RedisQueueService
from app.models import PredictionStatus


class TestMockPredictionService:
    """Test suite for mock prediction service."""
    
    @pytest.fixture
    def service(self):
        return MockPredictionService(min_delay=1, max_delay=2)  # Faster for testing
    
    def test_sync_prediction(self, service):
        """Test synchronous prediction."""
        start_time = time.time()
        result = service.mock_model_predict("test input")
        duration = time.time() - start_time
        
        assert isinstance(result, dict)
        assert "input" in result
        assert "result" in result
        assert result["input"] == "test input"
        assert result["result"].isdigit()
        assert 1 <= duration <= 3  # Account for processing time
    
    @pytest.mark.asyncio
    async def test_async_prediction(self, service):
        """Test asynchronous prediction."""
        start_time = time.time()
        result = await service.async_model_predict("test async input")
        duration = time.time() - start_time
        
        assert isinstance(result, dict)
        assert "input" in result
        assert "result" in result
        assert result["input"] == "test async input"
        assert result["result"].isdigit()
        assert 1 <= duration <= 3
    
    def test_performance_metrics(self, service):
        """Test performance metrics tracking."""
        initial_metrics = service.get_performance_metrics()
        
        # Perform a prediction
        service.mock_model_predict("test")
        
        updated_metrics = service.get_performance_metrics()
        
        assert updated_metrics["total_predictions"] > initial_metrics["total_predictions"]
        assert updated_metrics["total_processing_time"] > initial_metrics["total_processing_time"]
        assert updated_metrics["average_processing_time"] > 0


class TestRedisQueueService:
    """Test suite for Redis queue service."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for testing."""
        return MagicMock()
    
    @pytest.fixture
    def queue_service(self, mock_redis):
        """Queue service with mocked Redis."""
        service = RedisQueueService()
        service.redis_client = mock_redis
        return service
    
    def test_enqueue_prediction(self, queue_service, mock_redis):
        """Test prediction enqueueing."""
        mock_redis.xadd.return_value = "test-stream-id"
        mock_redis.setex.return_value = True
        
        result = queue_service.enqueue_prediction("test-id", "test input")
        
        assert result is True
        mock_redis.xadd.assert_called_once()
        mock_redis.setex.assert_called()
    
    def test_store_and_get_result(self, queue_service, mock_redis):
        """Test storing and retrieving prediction results."""
        test_result = {"input": "test", "result": "1234"}
        prediction_id = "test-prediction-id"
        
        # Mock successful storage
        mock_redis.setex.return_value = True
        result = queue_service.store_prediction_result(prediction_id, test_result)
        assert result is True
        
        # Mock successful retrieval
        import json
        mock_redis.get.return_value = json.dumps(test_result)
        retrieved = queue_service.get_prediction_result(prediction_id)
        assert retrieved == test_result
    
    def test_status_management(self, queue_service, mock_redis):
        """Test prediction status management."""
        prediction_id = "test-status-id"
        
        # Test setting status
        mock_redis.setex.return_value = True
        result = queue_service.set_prediction_status(prediction_id, PredictionStatus.PROCESSING)
        assert result is True
        
        # Test getting status
        mock_redis.get.return_value = "processing"
        status = queue_service.get_prediction_status(prediction_id)
        assert status == PredictionStatus.PROCESSING


class TestIntegration:
    """Integration tests for service interactions."""
    
    @pytest.mark.asyncio
    async def test_prediction_service_integration(self):
        """Test integration between prediction and queue services."""
        prediction_service = MockPredictionService(min_delay=0, max_delay=1)
        
        # Test that async prediction works
        result = await prediction_service.async_model_predict("integration test")
        
        assert isinstance(result, dict)
        assert "input" in result
        assert "result" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])