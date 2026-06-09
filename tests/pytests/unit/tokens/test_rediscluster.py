"""
Unit tests for the rediscluster eauth token storage.

These regression tests cover the bug where ``_redis_client`` used
``decode_responses=True``, which caused ``redis_client.get()`` and
``redis_client.keys()`` to return ``str``. Two callers in the same
module were then broken:

- ``get_token`` deserialises with ``salt.payload.loads``, which calls
  ``msgpack.unpackb`` under the hood; ``msgpack`` requires ``bytes``
  and raises ``TypeError`` for ``str``.
- ``list_tokens`` calls ``.decode("utf8")`` on each key, which
  ``str`` does not support.

Both errors were swallowed by a broad ``except Exception`` that
returned ``{}`` / ``[]``, so the bug was invisible to operators --
eauth tokens were never readable, but Salt logged a warning and
behaved as though the token simply did not exist.
"""

import pytest

import salt.payload
import salt.tokens.rediscluster as rediscluster_tokens
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rediscluster_tokens: {}}


@pytest.fixture
def patched_rediscluster():
    """
    Replace ``rediscluster.StrictRedisCluster`` with a factory that
    returns a controllable mock client. ``create=True`` covers
    environments where the optional ``rediscluster`` package is not
    installed (the symbol is then absent from the module under test).
    """
    fake_client = MagicMock(name="StrictRedisCluster_instance")
    fake_strict_cluster = MagicMock(
        name="StrictRedisCluster_class", return_value=fake_client
    )
    fake_rediscluster = MagicMock(
        name="rediscluster_module", StrictRedisCluster=fake_strict_cluster
    )

    with patch.object(
        rediscluster_tokens, "rediscluster", fake_rediscluster, create=True
    ):
        yield fake_strict_cluster, fake_client


@pytest.fixture
def fake_opts():
    return {"eauth_redis_host": "redis-cluster-1", "eauth_redis_port": 6379}


# ---------------------------------------------------------------------------
# _redis_client: decode_responses must NOT be enabled
# ---------------------------------------------------------------------------


def test_redis_client_does_not_enable_decode_responses(patched_rediscluster, fake_opts):
    """
    Headline regression: enabling ``decode_responses=True`` is what
    caused both ``get_token`` and ``list_tokens`` to fail. The fix
    removes that argument so the cluster client returns bytes for the
    msgpack-serialised values.
    """
    fake_strict_cluster, _ = patched_rediscluster
    rediscluster_tokens._redis_client(fake_opts)

    fake_strict_cluster.assert_called_once()
    kwargs = fake_strict_cluster.call_args.kwargs
    assert kwargs.get("decode_responses") is not True, (
        "decode_responses=True breaks salt.payload.loads (msgpack rejects "
        "str) and list_tokens (str has no .decode); this is the bug"
    )


# ---------------------------------------------------------------------------
# get_token: round-trip with msgpack bytes
# ---------------------------------------------------------------------------


def test_get_token_returns_full_data_for_existing_token(
    patched_rediscluster, fake_opts
):
    """
    The end-to-end check: with the fix, ``get_token`` reads the
    msgpack-serialised bytes from the cluster and returns the
    deserialised token data. Before the fix, ``redis_client.get``
    returned a ``str`` and ``msgpack.unpackb`` raised TypeError, which
    the broad ``except`` caught and turned into ``{}``.
    """
    _, fake_client = patched_rediscluster
    tdata = {"token": "abcd1234", "name": "alice", "eauth": "pam"}
    serialised = salt.payload.dumps(tdata)
    fake_client.get.return_value = serialised

    result = rediscluster_tokens.get_token(fake_opts, "abcd1234")
    assert result == tdata


def test_get_token_returns_empty_dict_for_missing_token(
    patched_rediscluster, fake_opts
):
    """
    When the cluster has no entry for the requested token, ``get``
    returns ``None`` and ``salt.payload.loads(None)`` raises; the
    function must keep its existing contract of returning ``{}`` in
    that case (used by callers as "no such token").
    """
    _, fake_client = patched_rediscluster
    fake_client.get.return_value = None

    result = rediscluster_tokens.get_token(fake_opts, "nonexistent")
    assert result == {}


# ---------------------------------------------------------------------------
# list_tokens: bytes keys decoded back to str
# ---------------------------------------------------------------------------


def test_list_tokens_returns_decoded_str_keys(patched_rediscluster, fake_opts):
    """
    With the fix, ``redis_client.keys()`` returns ``list[bytes]`` and
    the comprehension ``[k.decode("utf8") for k in ...]`` produces
    ``list[str]``. Before the fix, decode_responses=True made keys
    arrive as ``str`` already and ``str.decode("utf8")`` raised
    AttributeError, swallowed into ``[]``.
    """
    _, fake_client = patched_rediscluster
    fake_client.keys.return_value = [b"token-1", b"token-2", b"token-3"]

    result = rediscluster_tokens.list_tokens(fake_opts)
    assert result == ["token-1", "token-2", "token-3"]
    # And every element is genuinely a Python str, not bytes.
    assert all(isinstance(t, str) for t in result)


def test_list_tokens_returns_empty_when_no_tokens(patched_rediscluster, fake_opts):
    """No tokens in the cluster -> empty list. Pins backward compat."""
    _, fake_client = patched_rediscluster
    fake_client.keys.return_value = []

    result = rediscluster_tokens.list_tokens(fake_opts)
    assert result == []


# ---------------------------------------------------------------------------
# mk_token + get_token: round-trip with the same client
# ---------------------------------------------------------------------------


def test_mk_token_then_get_token_round_trip(patched_rediscluster, fake_opts):
    """
    End-to-end: ``mk_token`` writes msgpack bytes via ``set``;
    ``get_token`` reads them back via ``get`` and deserialises. With
    the fix, both ends agree on bytes; before the fix, ``get_token``
    received str and silently failed.
    """
    _, fake_client = patched_rediscluster

    # mk_token loops on .get to ensure the token does not already exist;
    # return None so the loop terminates immediately.
    fake_client.get.return_value = None

    tdata = {"name": "alice", "eauth": "pam"}
    minted = rediscluster_tokens.mk_token(fake_opts, tdata)
    assert "token" in minted
    assert minted["name"] == "alice"

    # mk_token must have called set() once with the msgpack-serialised
    # tdata as its second positional arg.
    fake_client.set.assert_called_once()
    set_args = fake_client.set.call_args.args
    stored_token, stored_payload = set_args
    assert stored_token == minted["token"]
    assert salt.payload.loads(stored_payload) == minted

    # Now simulate the read path: get returns the same payload bytes.
    fake_client.get.return_value = stored_payload
    fetched = rediscluster_tokens.get_token(fake_opts, stored_token)
    assert fetched == minted
