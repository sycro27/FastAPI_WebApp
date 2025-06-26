# app/services/queue.py

import redis
import json
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime
import uuid

from app.models import PredictionStatus

logger = logging.getLogger(__name__)


class RedisQueueService:
    def __init__(self, redis_url: str = None):
        # Get Redis URL from environment variable or use default
        if redis_url is None:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        logger.info(f"Connecting to Redis at: {redis_url}")
        
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test the connection
            self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
            
        self.stream_name = "prediction_tasks"
        self.consumer_group = "prediction_workers"
        self.consumer_name = f"worker_{uuid.uuid4().hex[:8]}"
        self.results_prefix = "prediction_result:"
        self.status_prefix = "prediction_status:"
        self.result_ttl = 86400  # 24 hours

    def setup_consumer_group(self):
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
        try:
            self.set_prediction_status(prediction_id, PredictionStatus.PENDING)
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
        try:
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
        try:
            self.redis_client.xack(self.stream_name, self.consumer_group, message_id)
            return True
        except Exception as e:
            logger.error(f"Failed to acknowledge task {message_id}: {e}")
            return False

    def store_prediction_result(self, prediction_id: str, result: Dict[str, str]) -> bool:
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
        try:
            status_key = f"{self.status_prefix}{prediction_id}"
            self.redis_client.setex(status_key, self.result_ttl, status.value)
            return True
        except Exception as e:
            logger.error(f"Failed to set status for {prediction_id}: {e}")
            return False

    def get_prediction_status(self, prediction_id: str) -> Optional[PredictionStatus]:
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
        try:
            pattern = f"{self.status_prefix}*"
            keys = self.redis_client.keys(pattern)
            cleaned = 0
            for key in keys:
                ttl = self.redis_client.ttl(key)
                if ttl == -1:
                    self.redis_client.expire(key, self.result_ttl)
                    cleaned += 1
            logger.info(f"Cleaned up {cleaned} entries")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to cleanup expired data: {e}")
            return 0

    def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Lazy singleton instance
_queue_service: Optional[RedisQueueService] = None

def get_queue_service() -> RedisQueueService:
    global _queue_service
    if _queue_service is None:
        _queue_service = RedisQueueService()
    return _queue_service