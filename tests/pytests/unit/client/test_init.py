import pytest

import salt.client
from salt.exceptions import SaltInvocationError
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


@pytest.mark.parametrize(
    "method,extra_kwargs",
    [
        ("get_cli_returns", {}),
        ("get_cli_static_event_returns", {}),
        ("get_cli_event_returns", {}),
    ],
)
def test_show_jid_goes_to_stderr(local_client, capsys, method, extra_kwargs):
    """
    When show_jid=True, the jid line must be printed to stderr, not stdout,
    so that --out=json output on stdout remains valid JSON.
    """
    jid = "20250101000000000001"

    with patch.object(local_client, "get_cache_returns", return_value={}), patch.object(
        local_client,
        "get_event_iter_returns",
        return_value=iter([]),
    ), patch.object(
        local_client,
        "get_iter_returns",
        return_value=iter([]),
    ), patch.dict(
        local_client.opts,
        {"timeout": 1, "gather_job_timeout": 1, "master_job_cache": "local_cache"},
    ), patch.object(
        local_client,
        "returners",
        {
            "local_cache.get_load": MagicMock(return_value={"tgt": "*"}),
        },
    ):
        func = getattr(local_client, method)
        result = func(jid, minions=[], show_jid=True, **extra_kwargs)
        # exhaust generator if needed
        if hasattr(result, "__iter__") and not isinstance(result, dict):
            list(result)

    captured = capsys.readouterr()
    assert f"jid: {jid}" in captured.err
    assert f"jid: {jid}" not in captured.out
