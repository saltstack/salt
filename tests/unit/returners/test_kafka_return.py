"""
Test module for Kafka returner
"""
import datetime
import random

import pytest
import salt.returners.kafka_return
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


@pytest.fixture
def configure_loader_modules():
    return {
        salt.returners.kafka_return: {
            "__opts__": {
                "id": "minion",
                "kafka.topic": "saltstack-tests",
                "kafka.bootstrap.servers": "server1:9092",
            }
        }
    }


def _get_producer_mock():
    producer = MagicMock()
    producer.poll = MagicMock(return_value=0)
    producer.produce = MagicMock(return_value=None)
    producer.flush = MagicMock(return_value=0)

    return MagicMock(return_value=producer)


def _return_data_factory(success=True):
    return {
        "id": salt.returners.kafka_return.__opts__["id"],
        "fun": "test.ping",
        "fun_args": [],
        "jid": "".join(str(random.randint(0, 9)) for _ in range(10)),
        "return": success,
    }


def _event_data_factory():
    jid = "".join(str(random.randint(0, 9)) for _ in range(10))

    return {
        "data": {
            "_stamp": datetime.datetime.now().isoformat(),
            "arg": [],
            "fun": "test.ping",
            "jid": jid,
            "minions": [salt.returners.kafka_return.__opts__["id"]],
            "missing": [],
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
        },
        "tag": "salt/job/{}/new".format(jid),
    }


class KafkaReturnerTestCase(TestCase):
    def test_options_defaults(self):
        options = salt.returners.kafka_return._get_options()

        assert options.get("topic", None) == "saltstack-tests"
        assert options.get("socket.timeout.ms", None) == 5000
        assert options.get("socket.keepalive.enable", None) is True
        assert options.get("message.send.max.retries", None) == 3
        assert options.get("bootstrap.servers", None) == "server1:9092"

    def test_returner(self):
        ret = _return_data_factory()
        _producer = _get_producer_mock()

        with patch(
            "salt.returners.kafka_return.Producer",
            new_callable=lambda: MagicMock(return_value=_producer),
            create=True,
        ):
            salt.returners.kafka_return.returner(ret)

            assert _producer.produce.called
            assert (
                _producer.produce.call_args[0][0]
                == salt.returners.kafka_return.__opts__["kafka.topic"]
            )
            assert _producer.produce.call_args[0][1] == salt.utils.json.dumps(ret)
            assert _producer.produce.call_args[0][
                2
            ] == salt.returners.kafka_return.__opts__["id"].encode("utf-8")
            assert "callback" in _producer.produce.call_args[1]

            assert _producer.flush.called
            assert _producer.flush.call_args[0][0] == 5

    def test_returner_error_handling(self):
        ret = _return_data_factory()
        _producer = _get_producer_mock()
        _producer.produce = MagicMock(return_value=None, side_effect=Exception)

        salt.returners.kafka_return.LOGGER = MagicMock()

        with patch(
            "salt.returners.kafka_return.Producer",
            new_callable=lambda: MagicMock(return_value=_producer),
            create=True,
        ), patch("salt.returners.kafka_return.KafkaException", Exception, create=True):
            salt.returners.kafka_return.returner(ret)

            assert not _producer.flush.called
            assert salt.returners.kafka_return.LOGGER.error.called
            assert (
                salt.returners.kafka_return.LOGGER.error.call_args[0][0]
                == "Failed to send return to Kafka"
            )

    def test_event_return(self):
        event = _event_data_factory()
        _producer = _get_producer_mock()

        with patch(
            "salt.returners.kafka_return.Producer",
            new_callable=lambda: MagicMock(return_value=_producer),
            create=True,
        ):
            salt.returners.kafka_return.event_return([event])

            assert _producer.produce.called
            assert (
                _producer.produce.call_args[0][0]
                == salt.returners.kafka_return.__opts__["kafka.topic"]
            )
            assert _producer.produce.call_args[0][1] == salt.utils.json.dumps(event)
            assert _producer.produce.call_args[0][
                2
            ] == salt.returners.kafka_return.__opts__["id"].encode("utf-8")
            assert "callback" in _producer.produce.call_args[1]

            assert _producer.flush.called
            assert _producer.flush.call_args[0][0] == 5

    def test_event_return_error_handling(self):
        event = _event_data_factory()
        _producer = _get_producer_mock()
        _producer.produce = MagicMock(return_value=None, side_effect=Exception)

        salt.returners.kafka_return.LOGGER = MagicMock()

        with patch(
            "salt.returners.kafka_return.Producer",
            new_callable=lambda: MagicMock(return_value=_producer),
            create=True,
        ), patch("salt.returners.kafka_return.KafkaException", Exception, create=True):
            salt.returners.kafka_return.event_return([event])

            assert not _producer.flush.called
            assert salt.returners.kafka_return.LOGGER.error.called
            assert (
                salt.returners.kafka_return.LOGGER.error.call_args[0][0]
                == "Failed to send event to Kafka"
            )

    def test_producer_init_error(self):
        ret = _return_data_factory()
        _producer = MagicMock(return_value=None, side_effect=Exception)

        salt.returners.kafka_return.LOGGER = MagicMock()

        with patch(
            "salt.returners.kafka_return.Producer", _producer, create=True
        ), patch("salt.returners.kafka_return.KafkaException", Exception, create=True):
            salt.returners.kafka_return.returner(ret)

            assert _producer.called
            assert salt.returners.kafka_return.LOGGER.error.called
            assert (
                "Failed to initialize Kafka producer"
                in salt.returners.kafka_return.LOGGER.error.call_args[0][0]
            )
