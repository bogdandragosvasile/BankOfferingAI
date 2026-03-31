"""Kafka consumer for the ``bank.transactions`` topic.

Consumes raw transaction messages, normalises them via
:func:`~data.kafka.consumers.normalizer.normalize_transaction`, and publishes
the result to the ``bank.transactions.normalized`` topic.
"""

from __future__ import annotations

import json
import logging
import os
import signal
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

from data.kafka.consumers.normalizer import normalize_transaction

logger = logging.getLogger(__name__)

_SOURCE_TOPIC = "bank.transactions"
_SINK_TOPIC = "bank.transactions.normalized"


def _build_consumer(bootstrap: str, group_id: str) -> Consumer:
    return Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )


def _build_producer(bootstrap: str) -> Producer:
    return Producer(
        {
            "bootstrap.servers": bootstrap,
            "acks": "all",
            "retries": 5,
            "retry.backoff.ms": 200,
        }
    )


def _delivery_report(err: KafkaError | None, msg: Any) -> None:
    if err:
        logger.error(
            "Delivery failed for transaction on %s [%d]: %s",
            msg.topic(),
            msg.partition(),
            err,
        )
    else:
        logger.debug(
            "Delivered to %s [%d] @ offset %d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


class TransactionConsumer:
    """Consumes ``bank.transactions``, normalises each record, and publishes
    to ``bank.transactions.normalized``."""

    def __init__(
        self,
        bootstrap: str | None = None,
        group_id: str = "transaction-consumer",
    ) -> None:
        self._bootstrap = bootstrap or os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
        self._group_id = group_id
        self._running = False
        self._stats: dict[str, int] = {
            "consumed": 0,
            "normalized": 0,
            "failed": 0,
            "published": 0,
        }

    def run(self) -> None:
        """Blocking consumer loop. Exits gracefully on SIGINT / SIGTERM."""
        signal.signal(signal.SIGINT, lambda *_: self._stop())
        signal.signal(signal.SIGTERM, lambda *_: self._stop())

        consumer = _build_consumer(self._bootstrap, self._group_id)
        producer = _build_producer(self._bootstrap)
        consumer.subscribe([_SOURCE_TOPIC])
        self._running = True

        logger.info("TransactionConsumer started — reading from %s", _SOURCE_TOPIC)

        try:
            while self._running:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                self._handle(msg, producer)
                consumer.commit(message=msg, asynchronous=False)

        finally:
            producer.flush(timeout=10)
            consumer.close()
            logger.info("TransactionConsumer stopped — stats: %s", self._stats)

    def _stop(self) -> None:
        self._running = False

    def _handle(self, msg: Any, producer: Producer) -> None:
        self._stats["consumed"] += 1

        try:
            raw: dict[str, Any] = json.loads(msg.value().decode("utf-8"))
        except Exception:
            logger.warning("Failed to deserialize message at offset %d", msg.offset())
            self._stats["failed"] += 1
            return

        try:
            normalized = normalize_transaction(raw)
        except Exception:
            logger.warning(
                "Normalization failed for transaction at offset %d: %s",
                msg.offset(),
                raw.get("transaction_id", "<unknown>"),
            )
            self._stats["failed"] += 1
            return

        self._stats["normalized"] += 1

        try:
            producer.produce(
                _SINK_TOPIC,
                key=(normalized.get("transaction_id") or "").encode("utf-8"),
                value=json.dumps(normalized).encode("utf-8"),
                callback=_delivery_report,
            )
            producer.poll(0)
            self._stats["published"] += 1
        except Exception:
            logger.exception(
                "Failed to publish normalized transaction %s",
                normalized.get("transaction_id"),
            )
            self._stats["failed"] += 1


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    TransactionConsumer().run()


if __name__ == "__main__":
    main()
