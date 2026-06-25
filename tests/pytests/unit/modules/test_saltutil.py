import pathlib

import pytest

import salt.modules.saltutil as saltutil
from salt.client import LocalClient
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.mock import sentinel as s


@pytest.fixture
def configure_loader_modules(minion_opts):
    minion_opts["file_client"] = "local"
    minion_opts["master_uri"] = "tcp://127.0.0.1:4505"
    return {
        saltutil: {
            "__opts__": minion_opts,
        }
    }


def test_exec_kwargs():
    _cmd_expected_kwargs = {
        "tgt": s.tgt,
        "fun": s.fun,
        "arg": s.arg,
        "timeout": s.timeout,
        "tgt_type": s.tgt_type,
        "ret": s.ret,
        "kwarg": s.kwarg,
    }
    client = create_autospec(LocalClient)

    saltutil._exec(client, **_cmd_expected_kwargs)
    client.cmd_iter.assert_called_with(**_cmd_expected_kwargs)

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"batch": s.batch},
    )
    client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset},
    )
    client.cmd_subset.assert_called_with(
        subset=s.subset, cli=True, **_cmd_expected_kwargs
    )

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset, "cli": s.cli},
    )
    client.cmd_subset.assert_called_with(
        subset=s.subset, cli=s.cli, **_cmd_expected_kwargs
    )

    # cmd_batch doesn't know what to do with 'subset', don't pass it along.
    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset, "batch": s.batch},
    )
    client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)


def test_refresh_grains_default_clean_pillar_cache():
    with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
        saltutil.refresh_grains()
        refresh_pillar.assert_called_with(clean_cache=False)


def test_refresh_grains_default_clean_pillar_cache_with_refresh_false():
    with patch("salt.modules.saltutil.refresh_modules") as refresh_modules:
        saltutil.refresh_grains(refresh_pillar=False)
        refresh_modules.assert_called()


def test_refresh_grains_clean_pillar_cache():
    with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
        saltutil.refresh_grains(clean_pillar_cache=True)
        refresh_pillar.assert_called_with(clean_cache=True)


def test_refresh_grains_clean_pillar_cache_with_refresh_false():
    with patch("salt.modules.saltutil.refresh_modules") as refresh_modules:
        saltutil.refresh_grains(clean_pillar_cache=True, refresh_pillar=False)
        refresh_modules.assert_called()


def test_sync_grains_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_grains()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_grains_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_grains(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)


def test_sync_pillar_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_pillar()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_pillar_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_pillar(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)


def test_sync_all_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_all()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_all_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_all(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)


def test_list_extmods(salt_call_cli, minion_opts):
    pathlib.Path(minion_opts["cachedir"], "extmods", "dummydir").mkdir(
        parents=True, exist_ok=True
    )
    ret = saltutil.list_extmods()
    assert "dummydir" in ret
    assert ret["dummydir"] == []


def test_refresh_beacons():
    ret = saltutil.refresh_beacons()
    assert ret is False


def test_refresh_matchers():
    ret = saltutil.refresh_matchers()
    assert ret is False


@pytest.mark.skip_on_windows
def test_refresh_modules_async_false():
    # XXX: This test adds coverage but what is it really testing? Seems we'd be
    # better off with at least a functional test here.
    kwargs = {"async": False}
    ret = saltutil.refresh_modules(**kwargs)
    assert ret is False


def test_clear_job_cache(salt_call_cli, minion_opts):
    pathlib.Path(minion_opts["cachedir"], "minion_jobs", "dummydir").mkdir(
        parents=True, exist_ok=True
    )
    ret = saltutil.clear_job_cache(hours=1)
    assert ret is True


@pytest.mark.destructive_test
def test_regen_keys(salt_call_cli, minion_opts):
    pathlib.Path(minion_opts["pki_dir"], "dummydir").mkdir(parents=True, exist_ok=True)
    saltutil.regen_keys()


# ---------------------------------------------------------------------------
# Running master-side functions (runner/wheel) as the master's configured user
# when invoked via saltutil on a minion that runs as a different user (#67716).
# ---------------------------------------------------------------------------


class _FakeClient:
    """Stand-in for RunnerClient/WheelClient with a controllable cmd()."""

    functions = {}

    def __init__(self, ret=None, exc=None):
        self._ret = ret
        self._exc = exc

    def cmd(self, name, **kwargs):
        if self._exc is not None:
            raise self._exc
        return self._ret


@pytest.mark.parametrize(
    "opts,euid,current_user,expected",
    (
        ({"user": "salt"}, 0, "root", "salt"),
        ({"user": "salt"}, 0, "salt", None),
        ({"user": "salt"}, 1000, "bob", None),
        ({"user": ""}, 0, "root", None),
        ({}, 0, "root", None),
    ),
)
def test_master_user_runas(opts, euid, current_user, expected):
    with patch("os.geteuid", return_value=euid), patch(
        "salt.utils.user.get_user", return_value=current_user
    ):
        assert saltutil._master_user_runas(opts) == expected


def test_client_cmd_as_returns_result():
    client = _FakeClient(ret={"local": True})
    with patch("salt.utils.user.chugid"):
        result = saltutil._client_cmd_as(
            "salt", client, "test.ping", {"arg": [], "kwarg": {}}
        )
    assert result == {"local": True}


def test_client_cmd_as_propagates_error():
    client = _FakeClient(exc=RuntimeError("boom"))
    with patch("salt.utils.user.chugid"):
        with pytest.raises(CommandExecutionError):
            saltutil._client_cmd_as(
                "salt", client, "test.ping", {"arg": [], "kwarg": {}}
            )


def test_runner_runs_as_master_user_when_needed():
    rclient = _FakeClient(ret="in-process")
    with patch.dict(saltutil.__opts__, {"master_job_cache": "local_cache"}):
        with patch("salt.runner.RunnerClient", return_value=rclient):
            with patch.object(saltutil, "_master_user_runas", return_value="salt"):
                with patch.object(
                    saltutil, "_client_cmd_as", return_value="dropped"
                ) as drop:
                    ret = saltutil.runner("test.ping")
    assert ret == "dropped"
    drop.assert_called_once()
    assert drop.call_args.args[0] == "salt"
    assert drop.call_args.args[2] == "test.ping"


def test_runner_runs_in_process_when_no_drop():
    rclient = MagicMock()
    rclient.functions = {}
    rclient.cmd.return_value = "in-process"
    with patch.dict(saltutil.__opts__, {"master_job_cache": "local_cache"}):
        with patch("salt.runner.RunnerClient", return_value=rclient):
            with patch.object(saltutil, "_master_user_runas", return_value=None):
                with patch.object(saltutil, "_client_cmd_as") as drop:
                    ret = saltutil.runner("test.ping")
    assert ret == "in-process"
    drop.assert_not_called()
    rclient.cmd.assert_called_once()


def test_wheel_runs_as_master_user_when_needed():
    wclient = _FakeClient(ret="in-process")
    with patch.dict(saltutil.__opts__, {"__role": "master"}):
        with patch("salt.wheel.WheelClient", return_value=wclient):
            with patch.object(saltutil, "_master_user_runas", return_value="salt"):
                with patch.object(
                    saltutil, "_client_cmd_as", return_value="dropped"
                ) as drop:
                    ret = saltutil.wheel("key.list_all")
    assert ret == "dropped"
    drop.assert_called_once()
    assert drop.call_args.args[0] == "salt"
    assert drop.call_args.args[2] == "key.list_all"


def test_wheel_runs_in_process_when_no_drop():
    wclient = MagicMock()
    wclient.functions = {}
    wclient.cmd.return_value = "in-process"
    with patch.dict(saltutil.__opts__, {"__role": "master"}):
        with patch("salt.wheel.WheelClient", return_value=wclient):
            with patch.object(saltutil, "_master_user_runas", return_value=None):
                with patch.object(saltutil, "_client_cmd_as") as drop:
                    ret = saltutil.wheel("key.list_all")
    assert ret == "in-process"
    drop.assert_not_called()
    wclient.cmd.assert_called_once()


@pytest.mark.skip_unless_on_linux
def test_client_cmd_as_drops_privileges_for_real():
    """
    End-to-end: the child actually changes to the target user. Requires root
    (to drop privileges) and a ``nobody`` account; skipped otherwise.
    """
    import os
    import pwd

    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        pytest.skip("requires root to drop privileges")
    try:
        target = pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("no 'nobody' account available")

    class _UidClient:
        functions = {}

        def cmd(self, name, **kwargs):
            return os.geteuid()

    assert saltutil._client_cmd_as("nobody", _UidClient(), "x", {}) == target.pw_uid
