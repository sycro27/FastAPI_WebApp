"""
Comprehensive test suite for prediction endpoints.
"""

import pytest
import asyncio
import uuid
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.services.prediction import prediction_service
from app.services.queue import queue_service
from app.models import PredictionStatus


class TestPredictionEndpoints:
    """Test suite for prediction API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    def test_sync_prediction_success(self, client):
        """Test successful synchronous prediction."""
        response = client.post(
            "/predict",
            json={"input": "test input data"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "input" in data
        assert "result" in data
        assert data["input"] == "test input data"
        assert data["result"].isdigit()
    
    def test_sync_prediction_empty_input(self, client):
        """Test synchronous prediction with empty input."""
        response = client.post(
            "/predict",
            json={"input": ""}
        )
        
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    
    def test_async_prediction_acceptance(self, client):
        """Test asynchronous prediction acceptance."""
        response = client.post(
            "/predict",
            json={"input": "test async input"},
            headers={"Async-Mode": "true"}
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "message" in data
        assert "prediction_id" in data
        assert "Processing asynchronously" in data["message"]
    
    def test_get_prediction_not_found(self, client):
        """Test getting result for non-existent prediction."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/predict/{fake_id}")
        
        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower()
    
    @patch('app.services.queue.queue_service.get_prediction_status')
    @patch('app.services.queue.queue_service.get_prediction_result')
    def test_get_prediction_completed(self, mock_get_result, mock_get_status, client):
        """Test getting completed prediction result."""
        prediction_id = str(uuid.uuid4())
        mock_get_status.return_value = PredictionStatus.COMPLETED
        mock_get_result.return_value = {"input": "test", "result": "1234"}
        
        response = client.get(f"/predict/{prediction_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["prediction_id"] == prediction_id
        assert "output" in data
        assert data["status"] == "completed"
    
    @patch('app.services.queue.queue_service.get_prediction_status')
    def test_get_prediction_processing(self, mock_get_status, client):
        """Test getting result for processing prediction."""
        prediction_id = str(uuid.uuid4())
        mock_get_status.return_value = PredictionStatus.PROCESSING
        
        response = client.get(f"/predict/{prediction_id}")
        
        assert response.status_code == 400
        assert "still being processed" in response.json()["error"]
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "services" in data
        assert "timestamp" in data
    
    def test_metrics_endpoint(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "prediction_service" in data
        assert "system" in data
        assert "timestamp" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "ZypherAI" in data["message"]
        assert "docs" in data


class TestAsyncFlow:
    """Test complete asynchronous prediction flow."""
    
    @pytest.mark.asyncio
    async def test_complete_async_flow(self):
        """Test complete async prediction workflow."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Submit async prediction
            response = await client.post(
                "/predict",
                json={"input": "test async flow"},
                headers={"Async-Mode": "true"}
            )
            
            assert response.status_code == 202
            prediction_id = response.json()["prediction_id"]
            
            # Wait a bit for processing to start
            await asyncio.sleep(0.1)
            
            # Check status (should be pending or processing)
            response = await client.get(f"/predict/{prediction_id}")
            assert response.status_code in [400, 200]  # Processing or completed


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_invalid_prediction_id_format(self, client):
        """Test invalid prediction ID format."""
        response = client.get("/predict/invalid")
        assert response.status_code == 400
    
    def test_very_long_input(self, client):
        """Test with very long input."""
        long_input = "x" * 20000  # Exceeds max length
        response = client.post(
            "/predict",
            json={"input": long_input}
        )
        assert response.status_code == 422  # Validation error
    
    def test_malformed_json(self, client):
        """Test with malformed JSON."""
        response = client.post(
            "/predict",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])