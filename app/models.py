"""
Used Pydantic models as data guards so that everything is structured and validated.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional
from enum import Enum


class PredictionStatus(str, Enum):
    """Enumeration for prediction processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PredictionRequest(BaseModel):
    """Request model for prediction input."""
    input: str = Field(..., min_length=1, max_length=10000, description="Input data for ML model prediction")

    class Config:
        schema_extra = {
            "example": {
                "input": "Sample input data for the model"
            }
        }


class SyncPredictionResponse(BaseModel):
    """Response model for synchronous predictions."""
    input: str = Field(..., description="Original input data")
    result: str = Field(..., description="Prediction result")

    class Config:
        schema_extra = {
            "example": {
                "input": "Sample input data for the model",
                "result": "1234"
            }
        }


class AsyncPredictionResponse(BaseModel):
    """Response model for asynchronous prediction acceptance."""
    message: str = Field(..., description="Status message")
    prediction_id: str = Field(..., description="Unique prediction identifier")

    class Config:
        schema_extra = {
            "example": {
                "message": "Request received. Processing asynchronously.",
                "prediction_id": "abc123"
            }
        }


class PredictionResult(BaseModel):
    """Response model for completed prediction results."""
    prediction_id: str = Field(..., description="Prediction identifier")
    output: Dict[str, str] = Field(..., description="Prediction output")
    status: PredictionStatus = Field(..., description="Processing status")

    class Config:
        schema_extra = {
            "example": {
                "prediction_id": "abc123",
                "output": {"input": "Sample input data", "result": "5678"},
                "status": "completed"
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error description")
    detail: Optional[str] = Field(None, description="Additional error details")

    class Config:
        schema_extra = {
            "example": {
                "error": "Prediction ID not found.",
                "detail": "The specified prediction ID does not exist in the system."
            }
        }