import pytest

import salt.client
from salt.exceptions import SaltClientError, SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def local_client():
    return salt.client.get_local_client()


def test_get_local_client(local_client):
    """
    Test that a local client is created
    """
    assert isinstance(local_client, salt.client.LocalClient)


def test_get_local_client_mopts(master_opts):
    master_opts["rest_cherrypy"] = {"port": 8000}
    local_client = salt.client.get_local_client(mopts=master_opts)
    assert isinstance(local_client, salt.client.LocalClient)
    assert local_client.opts == master_opts


@pytest.mark.parametrize(
    "val, expected",
    ((None, 5), (7, 7), ("9", 9), ("eleven", 5), (["13"], 5)),
)
def test_local_client_get_timeout(local_client, val, expected):
    assert local_client._get_timeout(timeout=val) == expected


@pytest.mark.parametrize(
    "val, expected",
    (
        ("group1", ["L@spongebob,patrick"]),
        ("group2", ["G@os:squidward"]),
        ("group3", ["(", "G@os:plankton", "and", "(", "L@spongebob,patrick", ")", ")"]),
    ),
)
def test_resolve_nodegroup(master_opts, val, expected):
    master_opts["nodegroups"] = {
        "group1": "L@spongebob,patrick",
        "group2": "G@os:squidward",
        "group3": "G@os:plankton and N@group1",
    }
    local_client = salt.client.get_local_client(mopts=master_opts)
    assert local_client._resolve_nodegroup(val) == expected


def test_resolve_nodegroup_error(master_opts):
    master_opts["nodegroups"] = {
        "group1": "L@spongebob,patrick",
        "group2": "G@os:squidward",
        "group3": "G@os:plankton and N@group1",
    }
    local_client = salt.client.get_local_client(mopts=master_opts)
    with pytest.raises(SaltInvocationError):
        local_client._resolve_nodegroup("missing")


def test_prep_pub(local_client):
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "*",
        "tgt_type": "glob",
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_kwargs(local_client):
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
        some_kwarg="spongebob",
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "*",
        "tgt_type": "glob",
        "user": local_client.salt_user,
        "kwargs": {
            "some_kwarg": "spongebob",
        },
    }
    assert result == expected


def test_prep_pub_start_event_kwarg_propagates(local_client):
    """
    A caller passing start_event=True must see it bundled into
    payload_kwargs["kwargs"] so the master sees it in clear_load and
    can propagate it to the published load.
    """
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
        start_event=True,
    )
    assert result["kwargs"] == {"start_event": True}


def test_prep_pub_start_event_kwarg_coexists_with_other_kwargs(local_client):
    """
    start_event must coexist with the other established passthrough
    kwargs (metadata, ret_config, ret_kwargs, module_executors) — the
    LocalClient does not give any of these special treatment beyond the
    generic kwargs bundling.
    """
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
        start_event=True,
        metadata={"ticket": "INC-1"},
        ret_config="syslog",
    )
    assert result["kwargs"] == {
        "start_event": True,
        "metadata": {"ticket": "INC-1"},
        "ret_config": "syslog",
    }


def test_prep_pub_omits_start_event_when_not_passed(local_client):
    """
    Without an explicit start_event kwarg, _prep_pub must not introduce
    one (no kwargs key at all when no kwargs were passed).
    """
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
    )
    assert "kwargs" not in result


def test_prep_pub_order_masters(master_opts):
    master_opts["order_masters"] = True
    local_client = salt.client.get_local_client(mopts=master_opts)
    result = local_client._prep_pub(
        tgt="*",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "*",
        "tgt_type": "glob",
        "to": 7,
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_nodegroup(master_opts):
    master_opts["nodegroups"] = {
        "group1": "L@spongebob,patrick",
        "group2": "G@os:squidward",
        "group3": "G@os:plankton and N@group1",
    }
    local_client = salt.client.get_local_client(mopts=master_opts)
    result = local_client._prep_pub(
        tgt="group1",
        fun="test.ping",
        arg="",
        tgt_type="nodegroup",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "L@spongebob,patrick",
        "tgt_type": "compound",
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_compound(local_client):
    result = local_client._prep_pub(
        tgt="spongebob,patrick",
        fun="test.ping",
        arg="",
        tgt_type="compound",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "spongebob,patrick",
        "tgt_type": "compound",
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_compound_nodegroup(master_opts):
    master_opts["nodegroups"] = {
        "group1": "L@spongebob,patrick",
        "group2": "G@os:squidward",
        "group3": "G@os:plankton and N@group1",
    }
    local_client = salt.client.get_local_client(mopts=master_opts)
    result = local_client._prep_pub(
        tgt="N@group1",
        fun="test.ping",
        arg="",
        tgt_type="compound",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "",
        "tgt": "L@spongebob,patrick",
        "tgt_type": "compound",
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_ext_job_cache(master_opts):
    master_opts["ext_job_cache"] = "mysql"
    local_client = salt.client.get_local_client(mopts=master_opts)
    result = local_client._prep_pub(
        tgt="spongebob,patrick",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "mysql",
        "tgt": "spongebob,patrick",
        "tgt_type": "glob",
        "user": local_client.salt_user,
    }
    assert result == expected


def test_prep_pub_ext_job_cache_existing(master_opts):
    master_opts["ext_job_cache"] = "mysql"
    local_client = salt.client.get_local_client(mopts=master_opts)
    result = local_client._prep_pub(
        tgt="spongebob,patrick",
        fun="test.ping",
        arg="",
        tgt_type="glob",
        ret="postgres",
        jid="123",
        timeout=7,
    )
    expected = {
        "arg": "",
        "cmd": "publish",
        "fun": "test.ping",
        "jid": "123",
        "key": "",
        "ret": "postgres,mysql",
        "tgt": "spongebob,patrick",
        "tgt_type": "glob",
        "user": local_client.salt_user,
    }
    assert result == expected


# ---------------------------------------------------------------------------
# LocalClient.pub / pub_async cluster_retry handling
#
# Clustered masters return ``{"enc": "clear", "load": {"ret": False,
# "cluster_retry": True}}`` while Raft is still forming / not a committed
# voter.  No ``jid`` key in the load, so the plain return at
# ``salt/client/__init__.py:2162`` (and the pub_async twin) would
# ``KeyError: 'jid'`` -- which ``cmd_async`` then re-raises as the
# useless ``SaltClientError: 'jid'``.  Observed on the 24-master
# clustered sandbox while Raft leadership churned.  The LocalClient
# publish path has never understood ``cluster_retry`` -- only the
# minion-side ``AsyncReqChannel._crypted_transfer`` does (see
# ``salt/channel/client.py:253-266``).
# ---------------------------------------------------------------------------


def _cluster_retry_payload():
    """Mirror the shape produced by ``ReqServerChannel.handle_message``
    at ``salt/channel/server.py:452`` when ``_cluster_is_ready()`` is
    False."""
    return {"enc": "clear", "load": {"ret": False, "cluster_retry": True}}


def test_pub_raises_clean_error_on_cluster_retry(local_client):
    """``LocalClient.pub`` must raise ``SaltClientError`` with a clear
    message when the master replies with the ``cluster_retry`` sentinel
    instead of ``KeyError: 'jid'``."""
    # ``ipc_mode: tcp`` skips the publish_pull.ipc existence check at
    # the top of ``pub()`` so the test can focus on the payload path.
    local_client.opts["ipc_mode"] = "tcp"
    local_client.opts["interface"] = "127.0.0.1"
    local_client.opts["ret_port"] = 4506

    channel_cm = MagicMock()
    channel_cm.__enter__.return_value.send.return_value = _cluster_retry_payload()

    with patch.object(
        salt.client.LocalClient, "_prep_pub", return_value={"cmd": "publish"}
    ), patch(
        "salt.channel.client.ReqChannel.factory", return_value=channel_cm
    ), patch.object(
        local_client.event, "connect_pub", return_value=True
    ):
        with pytest.raises(SaltClientError, match="cluster consensus still forming"):
            local_client.pub(
                tgt="*",
                fun="test.ping",
                arg=(),
                tgt_type="glob",
                ret="",
                jid="",
                timeout=5,
            )
