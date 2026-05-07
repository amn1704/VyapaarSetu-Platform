"""Optional Redpanda/Kafka publisher for production event streaming."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import settings

logger = logging.getLogger("ubid.event_bus")


async def publish_event(topic: str, payload: dict[str, Any]) -> bool:
    """
    Publish an event to Redpanda/Kafka when aiokafka is installed.

    The platform remains operational if the event bus is unavailable; database
    audit logs remain the source of truth.
    """
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        logger.info("aiokafka is not installed; skipping event publish to %s", topic)
        return False

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value, default=str).encode("utf-8"),
    )
    try:
        await producer.start()
        await producer.send_and_wait(topic, payload)
        return True
    except Exception as exc:
        logger.warning("Failed to publish event to %s: %s", topic, exc)
        return False
    finally:
        await producer.stop()
