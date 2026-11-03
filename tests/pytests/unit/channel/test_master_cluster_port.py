"""
Regression tests for https://github.com/saltstack/salt/issues/69877.

The Raft rewrite for master clustering accidentally read the peer-pool port
from ``cluster_port`` instead of the documented ``cluster_pool_port``.
``cluster_port`` was never registered in ``VALID_OPTS``/``DEFAULT_MASTER_OPTS``,
so ``.get("cluster_port", 55596)`` silently fell back to the hardcoded literal
``55596`` on every master, ignoring the operator's ``cluster_pool_port``
setting. This module locks in that ``MasterPubServerChannel.factory`` binds
the pool puller to ``opts["cluster_pool_port"]``.
"""

import salt.channel.server
from tests.support.mock import patch


def _cluster_opts(**overrides):
    opts = {
        "cluster_id": "test-cluster",
        "cluster_peers": [],
        "cluster_pool_port": 4520,
        "sock_dir": "/tmp/does-not-matter",
        "interface": "127.0.0.1",
        "publish_port": 4505,
    }
    opts.update(overrides)
    return opts


def test_master_pub_server_channel_factory_uses_cluster_pool_port():
    """
    ``MasterPubServerChannel.factory`` in cluster mode must bind the peer
    pool puller to ``opts["cluster_pool_port"]``, not the hardcoded 55596
    that the pre-fix code fell back to.
    """
    opts = _cluster_opts(cluster_pool_port=4520)

    with patch("salt.transport.tcp.PublishServer") as pub_server, patch.object(
        salt.channel.server.MasterPubServerChannel, "__init__", return_value=None
    ):
        salt.channel.server.MasterPubServerChannel.factory(opts)

    assert pub_server.called
    call_kwargs = pub_server.call_args.kwargs
    assert call_kwargs["pull_port"] == 4520
    assert call_kwargs["pull_port"] != 55596


def test_master_pub_server_channel_factory_honours_non_default_pool_port():
    """
    A non-default ``cluster_pool_port`` must be honored end-to-end. Before
    the fix this returned 55596 regardless of the operator's setting.
    """
    opts = _cluster_opts(cluster_pool_port=6520)

    with patch("salt.transport.tcp.PublishServer") as pub_server, patch.object(
        salt.channel.server.MasterPubServerChannel, "__init__", return_value=None
    ):
        salt.channel.server.MasterPubServerChannel.factory(opts)

    assert pub_server.call_args.kwargs["pull_port"] == 6520


def test_master_pub_server_channel_factory_ignores_cluster_port_key():
    """
    ``cluster_port`` is not a valid opt at the channel layer -- the alias
    lives in ``apply_master_config``, so once opts land at the factory the
    key must have been translated to ``cluster_pool_port``. If a caller
    passes ``cluster_port`` here, the factory must NOT fall back to it or
    to 55596; ``cluster_pool_port`` is the only source of truth.
    """
    opts = _cluster_opts(cluster_pool_port=4520)
    opts["cluster_port"] = 55596  # stale/typo -- must be ignored

    with patch("salt.transport.tcp.PublishServer") as pub_server, patch.object(
        salt.channel.server.MasterPubServerChannel, "__init__", return_value=None
    ):
        salt.channel.server.MasterPubServerChannel.factory(opts)

    assert pub_server.call_args.kwargs["pull_port"] == 4520
