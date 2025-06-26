"""
Redis-based queue service for scalable asynchronous task processing.
"""

import redis
import json
import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import uuid
from app.models import PredictionStatus

logger = logging.getLogger(__name__)


class RedisQueueService:
    """
    Redis Streams-based queue service for handling asynchronous predictions.
    Provides high-throughput, persistent task processing with consumer groups.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize Redis connection and configure streams.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.stream_name = "prediction_tasks"
        self.consumer_group = "prediction_workers"
        self.consumer_name = f"worker_{uuid.uuid4().hex[:8]}"
        self.results_prefix = "prediction_result:"
        self.status_prefix = "prediction_status:"
        
        # TTL for results (24 hours)
        self.result_ttl = 86400
        
        self._setup_consumer_group()
    
    def _setup_consumer_group(self) -> None:
        """
        Setup Redis consumer group for distributed processing.
        Creates group if it doesn't exist.
        """
        try:
            self.redis_client.xgroup_create(
                self.stream_name, 
                self.consumer_group, 
                id='0', 
                mkstream=True
            )
            logger.info(f"Created consumer group: {self.consumer_group}")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.info(f"Consumer group already exists: {self.consumer_group}")
            else:
                logger.error(f"Failed to create consumer group: {e}")
                raise
    
    def enqueue_prediction(self, prediction_id: str, input_data: str) -> bool:
        """
        Add prediction task to the queue.
        
        Args:
            prediction_id: Unique prediction identifier
            input_data: Input data for prediction
            
        Returns:
            True if successfully enqueued
        """
        try:
            # Set initial status
            self.set_prediction_status(prediction_id, PredictionStatus.PENDING)
            
            # Add task to stream
            task_data = {
                "prediction_id": prediction_id,
                "input_data": input_data,
                "created_at": datetime.utcnow().isoformat()
            }
            
            stream_id = self.redis_client.xadd(self.stream_name, task_data)
            logger.info(f"Enqueued prediction {prediction_id} with stream ID: {stream_id}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue prediction {prediction_id}: {e}")
            return False
    
    def get_next_task(self, timeout: int = 1000) -> Optional[Dict[str, Any]]:
        """
        Get next available task from the queue.
        
        Args:
            timeout: Timeout in milliseconds
            
        Returns:
            Task data or None if no tasks available
        """
        try:
            # Try to read new messages
            messages = self.redis_client.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_name: '>'},
                count=1,
                block=timeout
            )
            
            if messages:
                stream, msgs = messages[0]
                if msgs:
                    msg_id, fields = msgs[0]
                    return {
                        "message_id": msg_id,
                        "prediction_id": fields["prediction_id"],
                        "input_data": fields["input_data"],
                        "created_at": fields["created_at"]
                    }
            
            return None
        except Exception as e:
            logger.error(f"Failed to get next task: {e}")
            return None
    
    def acknowledge_task(self, message_id: str) -> bool:
        """
        Acknowledge task completion.
        
        Args:
            message_id: Stream message ID
            
        Returns:
            True if successfully acknowledged
        """
        try:
            self.redis_client.xack(self.stream_name, self.consumer_group, message_id)
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge task {message_id}: {e}")
            return False
    
    def store_prediction_result(self, prediction_id: str, result: Dict[str, str]) -> bool:
        """
        Store prediction result with TTL.
        
        Args:
            prediction_id: Prediction identifier
            result: Prediction result data
            
        Returns:
            True if successfully stored
        """
        try:
            result_key = f"{self.results_prefix}{prediction_id}"
            result_json = json.dumps(result)
            
            self.redis_client.setex(result_key, self.result_ttl, result_json)
            self.set_prediction_status(prediction_id, PredictionStatus.COMPLETED)
            
            logger.info(f"Stored result for prediction {prediction_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store result for {prediction_id}: {e}")
            return False
    
    def get_prediction_result(self, prediction_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieve prediction result.
        
        Args:
            prediction_id: Prediction identifier
            
        Returns:
            Prediction result or None if not found
        """
        try:
            result_key = f"{self.results_prefix}{prediction_id}"
            result_json = self.redis_client.get(result_key)
            
            if result_json:
                return json.loads(result_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get result for {prediction_id}: {e}")
            return None
    
    def set_prediction_status(self, prediction_id: str, status: PredictionStatus) -> bool:
        """
        Set prediction processing status.
        
        Args:
            prediction_id: Prediction identifier
            status: Processing status
            
        Returns:
            True if successfully set
        """
        try:
            status_key = f"{self.status_prefix}{prediction_id}"
            self.redis_client.setex(status_key, self.result_ttl, status.value)
            return True
        except Exception as e:
            logger.error(f"Failed to set status for {prediction_id}: {e}")
            return False
    
    def get_prediction_status(self, prediction_id: str) -> Optional[PredictionStatus]:
        """
        Get prediction processing status.
        
        Args:
            prediction_id: Prediction identifier
            
        Returns:
            Prediction status or None if not found
        """
        try:
            status_key = f"{self.status_prefix}{prediction_id}"
            status_value = self.redis_client.get(status_key)
            
            if status_value:
                return PredictionStatus(status_value)
            return None
        except Exception as e:
            logger.error(f"Failed to get status for {prediction_id}: {e}")
            return None
    
    def cleanup_expired_data(self) -> int:
        """
        Clean up expired prediction data.
        
        Returns:
            Number of cleaned up entries
        """
        try:
            # Redis TTL handles automatic cleanup, but we can manually clean up
            # any orphaned status entries
            pattern = f"{self.status_prefix}*"
            keys = self.redis_client.keys(pattern)
            
            cleaned = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    self.redis_client.expire(key, self.result_ttl)
                    cleaned += 1
            
            logger.info(f"Cleaned up {cleaned} entries")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}")
            return 0


# Global queue service instance
queue_service = RedisQueueService()