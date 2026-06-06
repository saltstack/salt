"""
Tests for salt.returners.redis_return
"""

import pytest

import salt.returners.redis_return as redis_return
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        redis_return: {
            "__opts__": {},
        },
    }


def test_returner_sets_minion_fun_key_with_ttl():
    """
    Regression test for #69038.

    The ``<minion>:<fun>`` last-jid pointer key written by ``returner`` must
    carry the same TTL as the rest of the returner data (``keep_jobs_seconds``);
    otherwise these keys accumulate in Redis indefinitely.
    """
    ttl = 1234
    ret = {
        "id": "minion-1",
        "jid": "20260504000000000001",
        "fun": "test.ping",
        "return": True,
        "success": True,
    }

    pipeline = MagicMock()
    serv = MagicMock()
    serv.pipeline.return_value = pipeline

    with patch.object(redis_return, "_get_serv", return_value=serv), patch.object(
        redis_return, "_get_ttl", return_value=ttl
    ):
        redis_return.returner(ret)

    # The <minion>:<fun> key must be written with an expiry equal to the TTL
    # used for the rest of the returner data. Accept either the kwarg form
    # ``ex=ttl`` or the legacy second-positional-arg form, so the fix can use
    # whichever idiom the module prefers.
    found_with_ttl = False
    for c in pipeline.set.call_args_list:
        args, kwargs = c
        if not args or args[0] != "minion-1:test.ping":
            continue
        if kwargs.get("ex") == ttl:
            found_with_ttl = True
            break
    assert found_with_ttl, (
        "returner() must call pipeline.set('minion-1:test.ping', jid, ex=<ttl>) "
        "so the key inherits keep_jobs_seconds; saw calls: "
        f"{pipeline.set.call_args_list!r}"
    )
