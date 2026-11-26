"""
Verify that ``RemotePillar.compile_pillar`` and
``AsyncRemotePillar.compile_pillar`` return a plain Python ``dict``
(not a ``MaskedDict``).
"""

import pytest

import salt.pillar
from salt.utils.secret import MaskedDict, MaskedList
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def minion_opts():
    return {
        "id": "testminion",
        "saltenv": "base",
        "pillarenv": None,
        "pillar_mask_output": False,
        "transport": "zeromq",
        "__role": "minion",
    }


def _mk_sync_channel(payload):
    ch = MagicMock()
    ch.crypted_transfer_decode_dictentry = MagicMock(return_value=payload)
    return ch


def _mk_async_channel(payload):
    ch = MagicMock()
    ch.crypted_transfer_decode_dictentry = AsyncMock(return_value=payload)
    return ch


class TestRemotePillarCompilePlain:
    def test_sync_returns_plain_dict(self, minion_opts):
        """
        ``RemotePillar.compile_pillar`` returns the channel payload
        unchanged; it must no longer wrap it in ``MaskedDict``.
        """
        plain = {"a": 1, "db": {"root_password": "hunter2"}}
        with patch(
            "salt.channel.client.ReqChannel.factory",
            return_value=_mk_sync_channel(plain),
        ):
            rp = salt.pillar.RemotePillar(
                minion_opts,
                {},
                minion_opts["id"],
                "base",
            )
            with patch.object(rp, "validate_return", MagicMock()):
                compiled = rp.compile_pillar()

        assert isinstance(compiled, dict)
        assert not isinstance(compiled, MaskedDict)
        assert type(compiled) is dict
        assert compiled == plain
        # Nested dict must also be plain, not MaskedDict
        assert type(compiled["db"]) is dict
        assert not isinstance(compiled["db"], MaskedDict)

    def test_sync_does_not_mask_list_leaves(self, minion_opts):
        plain = {"hosts": ["h1", "h2"]}
        with patch(
            "salt.channel.client.ReqChannel.factory",
            return_value=_mk_sync_channel(plain),
        ):
            rp = salt.pillar.RemotePillar(
                minion_opts,
                {},
                minion_opts["id"],
                "base",
            )
            with patch.object(rp, "validate_return", MagicMock()):
                compiled = rp.compile_pillar()

        assert type(compiled["hosts"]) is list
        assert not isinstance(compiled["hosts"], MaskedList)


class TestAsyncRemotePillarCompilePlain:
    async def test_async_returns_plain_dict(self, minion_opts):
        plain = {"api_key": "sk-abc", "db": {"root_password": "hunter2"}}
        with patch(
            "salt.channel.client.AsyncReqChannel.factory",
            return_value=_mk_async_channel(plain),
        ):
            rp = salt.pillar.AsyncRemotePillar(
                minion_opts,
                {},
                minion_opts["id"],
                "base",
            )
            with patch.object(rp, "validate_return", MagicMock()):
                compiled = await rp.compile_pillar()

        assert isinstance(compiled, dict)
        assert not isinstance(compiled, MaskedDict)
        assert type(compiled) is dict
        assert compiled == plain
        # Nested containers not wrapped either
        assert not isinstance(compiled["db"], MaskedDict)

    async def test_async_scalar_leaves_unchanged(self, minion_opts):
        plain = {"password": "hunter2"}
        with patch(
            "salt.channel.client.AsyncReqChannel.factory",
            return_value=_mk_async_channel(plain),
        ):
            rp = salt.pillar.AsyncRemotePillar(
                minion_opts,
                {},
                minion_opts["id"],
                "base",
            )
            with patch.object(rp, "validate_return", MagicMock()):
                compiled = await rp.compile_pillar()

        assert compiled["password"] == "hunter2"
        # Plain str; no masked proxy
        assert isinstance(compiled["password"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
