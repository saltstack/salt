"""
Unit tests for the Redis returner.
"""

import json

import salt.returners.redis_return as redis_return
from tests.support.mock import MagicMock, patch


def test_get_fun_reads_from_ret_hash():
    serv = MagicMock()
    serv.smembers.return_value = {"minion-1"}
    serv.get.side_effect = lambda key: "20260504010203040506" if key == "minion-1:test.ping" else None
    serv.hget.return_value = json.dumps(
        {
            "jid": "20260504010203040506",
            "fun": "test.ping",
            "id": "minion-1",
            "return": True,
        }
    )

    with patch.object(redis_return, "_get_serv", return_value=serv):
        assert redis_return.get_fun("test.ping") == {
            "minion-1": {
                "jid": "20260504010203040506",
                "fun": "test.ping",
                "id": "minion-1",
                "return": True,
            }
        }

    serv.get.assert_called_once_with("minion-1:test.ping")
    serv.hget.assert_called_once_with("ret:20260504010203040506", "minion-1")


def test_get_jid_reads_ret_hash():
    serv = MagicMock()
    serv.hgetall.return_value = {
        "minion-1": json.dumps(
            {
                "jid": "20260504010203040506",
                "fun": "test.ping",
                "id": "minion-1",
                "return": True,
            }
        )
    }

    with patch.object(redis_return, "_get_serv", return_value=serv):
        assert redis_return.get_jid("20260504010203040506") == {
            "minion-1": {
                "jid": "20260504010203040506",
                "fun": "test.ping",
                "id": "minion-1",
                "return": True,
            }
        }

    serv.hgetall.assert_called_once_with("ret:20260504010203040506")