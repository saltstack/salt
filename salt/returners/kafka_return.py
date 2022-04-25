"""
Return data to a Kafka topic

:maintainer: Justin Desilets (justin.desilets@gmail.com)
:maturity: 20181119
:depends: confluent-kafka
:platform: all

To enable this returner install confluent-kafka and enable the following
settings in the minion config:

    returner.kafka.bootstrap:
      - "server1:9092"
      - "server2:9092"
      - "server3:9092"

    returner.kafka.topic: 'topic'

To use the kafka returner, append `--return kafka` to the Salt command, eg;

    salt '*' test.ping --return kafka

"""

import logging

import salt.utils.json

try:
    from confluent_kafka import Producer

    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False

log = logging.getLogger(__name__)


__virtualname__ = "kafka"


def __virtual__():
    if not HAS_KAFKA:
        return (
            False,
            "Could not import kafka returner; confluent-kafka is not installed.",
        )
    return __virtualname__


def _get_conn():
    """
    Return a kafka connection
    """
    if __salt__["config.option"]("returner.kafka.bootstrap"):
        bootstrap = ",".join(__salt__["config.option"]("returner.kafka.bootstrap"))
    else:
        log.error("Unable to find kafka returner config option: bootstrap")
        return None
    return bootstrap


def _delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result.
    Triggered by poll() or flush()."""
    if err is not None:
        log.error("Message delivery failed: %s", err)
    else:
        log.debug("Message delivered to %s [%s]", msg.topic(), msg.partition())


def returner(ret):
    """
    Return information to a Kafka server
    """
    if __salt__["config.option"]("returner.kafka.topic"):
        topic = __salt__["config.option"]("returner.kafka.topic")

        conn = _get_conn()
        producer = Producer({"bootstrap.servers": conn})
        producer.poll(0)
        producer.produce(
            topic,
            salt.utils.json.dumps(ret),
            str(ret).encode("utf-8"),
            callback=_delivery_report,
        )

        producer.flush()
    else:
        log.error("Unable to find kafka returner config option: topic")
