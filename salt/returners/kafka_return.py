"""
Return data to a Kafka topic

:maintainer: Justin Desilets <justin.desilets@gmail.com>, Zane Mingee <zmingee@gmail.com>
:maturity: stable
:depends: ``confluent-kafka``
:platform: all

The following options are enabled by default:

.. code-block:: yaml

    kafka.topic: "saltstack"
    kafka.socket.timeout.ms: 5000
    kafka.socket.keepalive.enable: true
    kafka.message.send.max.retries: 3

Configuration options are automatically passed to the Kafka Producer. Options
must be prefixed with "``kafka.``". For a list of all options available, please
refer to the `librdkafka documentation`_.

.. _librdkafka documentation: https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md

To use the Kafka job returner, append `--return kafka` to the Salt command:

    salt '*' test.ping --return kafka

To use the Kafka job returner for all job returns, the
:conf_master:`ext_job_cache` or :conf_master:`master_job_cache` options may
be set to ``kafka``. For more information, please see
:ref:`external-job-cache`.

To use the Kafka event returner, set the :conf_master:`event_return` option to
``kafka``.

"""

import copy
import logging

import salt.returners
import salt.utils.json
import salt.utils.stringutils

try:
    from confluent_kafka import Producer, KafkaException

    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False

LOGGER = logging.getLogger(__name__)


__virtualname__ = "kafka"


def __virtual__():
    if not HAS_KAFKA:
        return (
            False,
            "Could not import kafka returner; confluent-kafka is not installed.",
        )
    return __virtualname__


def _get_options(ret=None):
    defaults = {
        "topic": "saltstack",
        "socket.timeout.ms": 5000,
        "socket.keepalive.enable": True,
        "message.send.max.retries": 3,
    }
    _options = copy.deepcopy(defaults)

    cfg = __salt__.get("config.option", __opts__)
    if isinstance(cfg, dict):
        c_cfg = cfg
    else:
        c_cfg = cfg("{}.*".format(__virtualname__), wildcard=True)

    ret_config = salt.returners._fetch_ret_config(ret)

    for option in c_cfg:
        key = option[len(__virtualname__ + ".") :]
        value = salt.returners._fetch_option(c_cfg, ret_config, __virtualname__, option)

        if isinstance(value, bool):
            _options[key] = str(value).lower()
        else:
            _options[key] = value

    LOGGER.debug("Kafka returner options:\n%s", _options)

    return _options


def _get_producer(_options=None):
    """
    Return a kafka connection
    """

    if _options is None:
        _options = _get_options()

    producer = Producer(**{k: v for (k, v) in _options.items() if v is not None})
    producer.poll(_options["socket.timeout.ms"] / 1000)

    return producer


def _delivery_report(err, msg):
    """ Called once for each message produced to indicate delivery result.
        Triggered by poll() or flush(). """
    if err is not None:
        LOGGER.error("Message delivery failed: %s", err)
    else:
        LOGGER.debug("Message delivered to %s [%s]", msg.topic(), msg.partition())


def returner(ret):
    """
    Return information to a Kafka server
    """
    _options = _get_options(ret)
    topic = _options.pop("topic")

    try:
        producer = _get_producer(_options)
    except KafkaException as exc:
        if exc.args:
            LOGGER.error("Failed to initialize Kafka producer: %s", exc.args[0].str())
        else:
            LOGGER.error("Failed to initialize Kafka producer")
        return

    try:
        producer.produce(
            topic,
            salt.utils.json.dumps(ret),
            ret["id"].encode("utf-8"),
            callback=_delivery_report,
        )
        producer.flush(_options["socket.timeout.ms"] / 1000)
    except (BufferError, KafkaException):
        LOGGER.error("Failed to send return to Kafka")


def event_return(events):
    """
    Return event to Kafka server
    """
    _options = _get_options()
    topic = _options.pop("topic")

    try:
        producer = _get_producer(_options)
    except KafkaException as exc:
        if exc.args:
            LOGGER.error("Failed to initialize Kafka producer: %s", exc.args[0].str())
        else:
            LOGGER.error("Failed to initialize Kafka producer")
        return

    try:
        for event in events:
            tag = event.get("tag", "")
            data = event.get("data", "")

            producer.produce(
                topic,
                salt.utils.json.dumps(event),
                __opts__["id"].encode("utf-8"),
                callback=_delivery_report,
            )

        producer.flush(_options["socket.timeout.ms"] / 1000)
    except (BufferError, KafkaException):
        LOGGER.error("Failed to send event to Kafka")
