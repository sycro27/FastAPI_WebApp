"""
Prediction API endpoints with comprehensive error handling and validation.
"""

import uuid
import asyncio
import logging
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks
from typing import Optional, Union

from app.models import (
    PredictionRequest, 
    SyncPredictionResponse, 
    AsyncPredictionResponse,
    PredictionResult,
    ErrorResponse,
    PredictionStatus
)
from app.services.prediction import prediction_service
from app.services.queue import get_queue_service

logger = logging.getLogger(__name__)

# Create router with prefix and tags for OpenAPI documentation
router = APIRouter(prefix="/predict", tags=["predictions"])

# Get the queue service instance
queue_service = get_queue_service()


@router.post(
    "",
    response_model=Union[SyncPredictionResponse, AsyncPredictionResponse],
    responses={
        200: {"model": SyncPredictionResponse, "description": "Synchronous prediction completed"},
        202: {"model": AsyncPredictionResponse, "description": "Asynchronous prediction accepted"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Run ML Model Prediction",
    description="Execute prediction either synchronously or asynchronously based on Async-Mode header"
)
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    async_mode: Optional[str] = Header(None, alias="Async-Mode")
) -> Union[SyncPredictionResponse, AsyncPredictionResponse]:
    """
    Main prediction endpoint supporting both sync and async modes.
    
    - **Synchronous mode**: Processes immediately and returns result
    - **Asynchronous mode**: Returns prediction ID and processes in background
    
    Args:
        request: Prediction input data
        background_tasks: FastAPI background task manager
        async_mode: Header to enable asynchronous processing
        
    Returns:
        Either immediate prediction result or async acceptance response
        
    Raises:
        HTTPException: For various error conditions
    """
    try:
        # Validate input length and content
        if len(request.input.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Input cannot be empty"
            )
        
        # Check if async mode is requested
        is_async = async_mode is not None and async_mode.lower() == "true"
        
        if is_async:
            # Asynchronous processing
            prediction_id = str(uuid.uuid4())
            
            # Enqueue the prediction task
            success = queue_service.enqueue_prediction(prediction_id, request.input)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to enqueue prediction task"
                )
            
            # Start background processing
            background_tasks.add_task(process_async_prediction, prediction_id, request.input)
            
            logger.info(f"Accepted async prediction request: {prediction_id}")
            
            return AsyncPredictionResponse(
                message="Request received. Processing asynchronously.",
                prediction_id=prediction_id
            )
        else:
            # Synchronous processing
            logger.info(f"Processing sync prediction for input: {request.input[:50]}...")
            
            result = prediction_service.mock_model_predict(request.input)
            
            return SyncPredictionResponse(
                input=result["input"],
                result=result["result"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in predict endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred"
        )


@router.get(
    "/{prediction_id}",
    response_model=PredictionResult,
    responses={
        200: {"model": PredictionResult, "description": "Prediction completed"},
        400: {"model": ErrorResponse, "description": "Prediction still processing"},
        404: {"model": ErrorResponse, "description": "Prediction ID not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get Prediction Result",
    description="Retrieve the result of an asynchronous prediction by ID"
)
async def get_prediction_result(prediction_id: str) -> PredictionResult:
    """
    Retrieve prediction result by ID.
    
    Args:
        prediction_id: Unique prediction identifier
        
    Returns:
        Prediction result with status
        
    Raises:
        HTTPException: For various error conditions
    """
    try:
        # Validate prediction ID format
        if not prediction_id or len(prediction_id) < 8:
            raise HTTPException(
                status_code=400,
                detail="Invalid prediction ID format"
            )
        
        # Check prediction status
        status = queue_service.get_prediction_status(prediction_id)
        if status is None:
            raise HTTPException(
                status_code=404,
                detail="Prediction ID not found."
            )
        
        # If still processing, return appropriate error
        if status in [PredictionStatus.PENDING, PredictionStatus.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail="Prediction is still being processed."
            )
        
        # If failed, return error
        if status == PredictionStatus.FAILED:
            raise HTTPException(
                status_code=500,
                detail="Prediction processing failed."
            )
        
        # Get completed result
        result = queue_service.get_prediction_result(prediction_id)
        if result is None:
            # This shouldn't happen if status is completed, but handle gracefully
            raise HTTPException(
                status_code=500,
                detail="Prediction result not available."
            )
        
        logger.info(f"Retrieved result for prediction: {prediction_id}")
        
        return PredictionResult(
            prediction_id=prediction_id,
            output=result,
            status=status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving prediction {prediction_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error occurred"
        )


async def process_async_prediction(prediction_id: str, input_data: str) -> None:
    """
    Background task for processing asynchronous predictions.
    
    Args:
        prediction_id: Unique prediction identifier
        input_data: Input data for prediction
    """
    try:
        logger.info(f"Starting async processing for prediction: {prediction_id}")
        
        # Update status to processing
        queue_service.set_prediction_status(prediction_id, PredictionStatus.PROCESSING)
        
        # Process the prediction
        result = await prediction_service.async_model_predict(input_data)
        
        # Store the result
        success = queue_service.store_prediction_result(prediction_id, result)
        if not success:
            logger.error(f"Failed to store result for prediction: {prediction_id}")
            queue_service.set_prediction_status(prediction_id, PredictionStatus.FAILED)
        else:
            logger.info(f"Completed async processing for prediction: {prediction_id}")
            
    except Exception as e:
        logger.error(f"Error processing async prediction {prediction_id}: {e}")
        queue_service.set_prediction_status(prediction_id, PredictionStatus.FAILED)