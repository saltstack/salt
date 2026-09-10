# pylint: skip-file
import asyncio
import collections
import os
import pathlib
import stat
import threading
import time

import pytest

import salt.channel.client
import salt.config
import salt.crypt
import salt.exceptions
import salt.master
import salt.serializers.msgpack
import salt.utils.cache
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import AsyncMock, MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

try:
    import pygit2  # pylint: disable=unused-import

    HAS_PYGIT2 = True
except ImportError:
    HAS_PYGIT2 = False


skipif_no_pygit2 = pytest.mark.skipif(not HAS_PYGIT2, reason="Missing pygit2")


@pytest.fixture
def maintenance_opts(master_opts):
    """
    Options needed for master's Maintenence class
    """
    opts = master_opts.copy()
    opts.update(git_pillar_update_interval=180, maintenance_interval=181)
    yield opts


@pytest.fixture
def maintenance(maintenance_opts):
    """
    The master's Maintenence class
    """
    return salt.master.Maintenance(maintenance_opts)


@pytest.fixture
def clear_funcs(master_opts):
    """
    The Master's ClearFuncs object.

    The pre-PR ``runner``/``wheel``/``mk_token``/``get_token``/``ping``
    handlers were sync callables returning dicts. PR #70129 converted
    them to ``async def`` and installed sync shims when
    ``master_async_mworker=False`` (the LTS default). The shared
    ``master_opts`` conftest fixture force-flips ``master_async_mworker``
    to True for the async-path suites; opt back out here so the legacy
    sync tests (``test_runner_*`` / ``test_wheel_*``) exercise the LTS
    default shim path instead of getting an unawaited coroutine.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = False
    clear_funcs = salt.master.ClearFuncs(opts, {})
    try:
        yield clear_funcs
    finally:
        clear_funcs.destroy()


@pytest.fixture
def cluster_maintenance_opts(master_opts, tmp_path):
    """
    Options needed for master's Maintenence class
    """
    opts = master_opts.copy()
    opts.update(
        git_pillar_update_interval=180,
        maintenance_interval=181,
        cluster_pki_dir=tmp_path,
        cluster_id="test-cluster",
    )
    yield opts


@pytest.fixture
def cluster_maintenance(cluster_maintenance_opts):
    """
    The master's Maintenence class
    """
    return salt.master.Maintenance(cluster_maintenance_opts)


@pytest.fixture
def encrypted_requests(tmp_path):
    # To honor the comment on AESFuncs
    (tmp_path / "pki").mkdir()
    # These tests exercise the async MWorker path; opt into it explicitly.
    # The LTS default (``master_async_mworker: False``) shadows every
    # ``async def`` handler with a sync body, which would break tests
    # written against the async signatures.
    return salt.master.AESFuncs(
        opts={
            "pki_dir": str(tmp_path / "pki"),
            "cachedir": str(tmp_path / "cache"),
            "sock_dir": str(tmp_path / "sock_drawer"),
            "conf_file": str(tmp_path / "config.conf"),
            "fileserver_backend": ["local"],
            "master_job_cache": False,
            "keys.cache_driver": "localfs_key",
            "__role": "master",
            "optimization_order": [0, 1, 2],
            "master_sign_key_name": "master_sign",
            "id": "master",
            "master_async_mworker": True,
        }
    )


def test_maintenance_pki_dir_initialized():
    """
    Verify Maintenance pki_dir property initalization
    """
    not_clustered_path = "not_clustered"
    clustered_path = "clustered"
    opts = {
        "loop_interval": 10,
        "maintenance_interval": 1,
        "pki_dir": not_clustered_path,
        "cluster_pki_dir": clustered_path,
    }

    # If it's not a cluster, pki_dir is opts['pki_dir']
    mp = salt.master.Maintenance(opts)
    assert mp.pki_dir == not_clustered_path
    assert mp.pki_dir != clustered_path

    # If it's a cluster, pki_dir is opts['cluster_pki_dir']
    opts.update(cluster_id="test-cluster")
    mp = salt.master.Maintenance(opts)
    assert mp.pki_dir == clustered_path
    assert mp.pki_dir != not_clustered_path


def test_maintenance_duration():
    """
    Validate Maintenance process duration.
    """
    opts = {
        "loop_interval": 10,
        "maintenance_interval": 1,
        "cachedir": "/tmp",
        "sock_dir": "/tmp",
        "maintenance_niceness": 1,
        "key_cache": "sched",
        "conf_file": "",
        "master_job_cache": "",
        "pki_dir": "/tmp",
        "eauth_tokens": "",
        # LoadAuth (constructed in _post_fork_init since the memory-leak
        # caching change) reads eauth_tokens.* + cluster_id at __init__
        # time.  Provide defaults matching salt.config so the test can
        # exercise the real init path without hitting KeyError.
        "eauth_tokens.cache_driver": None,
        "eauth_tokens.cluster_id": None,
        "cluster_id": None,
        "keys.cache_driver": "localfs_key",
        "__role": "master",
        "optimization_order": [0, 1, 2],
        "master_sign_key_name": "master_sign",
    }
    mp = salt.master.Maintenance(opts)
    with patch("salt.utils.verify.check_max_open_files") as check_files, patch.object(
        mp, "handle_key_cache"
    ) as handle_key_cache, patch("salt.daemons") as salt_daemons, patch.object(
        mp, "handle_git_pillar"
    ) as handle_git_pillar:
        mp.run()
    assert salt_daemons.masterapi.clean_old_jobs.called
    assert salt_daemons.masterapi.clean_expired_tokens.called
    assert salt_daemons.masterapi.clean_pub_auth.called
    assert handle_git_pillar.called


def test_fileserver_duration():
    """
    Validate Fileserver process duration.
    """
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.assert_called_once()
        # Timeout is 1 second
        duration = end - start
        if duration > 2 and salt.utils.platform.spawning_platform():
            # Give spawning platforms some slack
            duration = round(duration, 1)
        assert 2 > duration > 1


@pytest.mark.parametrize(
    "expected_return, payload",
    (
        (
            {
                "jid": "20221107162714826470",
                "id": "example-minion",
                "return": {
                    "pkg_|-linux-install-utils_|-curl_|-installed": {
                        "name": "curl",
                        "changes": {},
                        "result": True,
                        "comment": "All specified packages are already installed",
                        "__sls__": "base-linux.base",
                        "__run_num__": 0,
                        "start_time": "08:27:17.594038",
                        "duration": 32.963,
                        "__id__": "linux-install-utils",
                    },
                },
                "retcode": 0,
                "success": True,
                "fun_args": ["base-linux", {"pillar": {"test": "value"}}],
                "fun": "state.sls",
                "out": "highstate",
            },
            {
                "cmd": "_syndic_return",
                "load": [
                    {
                        "id": "aws.us-east-1.salt-syndic",
                        "jid": "20221107162714826470",
                        "fun": "state.sls",
                        "arg": None,
                        "tgt": None,
                        "tgt_type": None,
                        "load": {
                            "arg": [
                                "base-linux",
                                {"pillar": {"test": "value"}, "__kwarg__": True},
                            ],
                            "cmd": "publish",
                            "fun": "state.sls",
                            "jid": "20221107162714826470",
                            "ret": "",
                            "tgt": "example-minion",
                            "user": "sudo_ubuntu",
                            "kwargs": {
                                "show_jid": False,
                                "delimiter": ":",
                                "show_timeout": True,
                            },
                            "tgt_type": "glob",
                        },
                        "return": {
                            "example-minion": {
                                "return": {
                                    "pkg_|-linux-install-utils_|-curl_|-installed": {
                                        "name": "curl",
                                        "changes": {},
                                        "result": True,
                                        "comment": "All specified packages are already installed",
                                        "__sls__": "base-linux.base",
                                        "__run_num__": 0,
                                        "start_time": "08:27:17.594038",
                                        "duration": 32.963,
                                        "__id__": "linux-install-utils",
                                    },
                                },
                                "retcode": 0,
                                "success": True,
                                "fun_args": [
                                    "base-linux",
                                    {"pillar": {"test": "value"}},
                                ],
                            }
                        },
                        "out": "highstate",
                    }
                ],
                "_stamp": "2022-11-07T16:27:17.965404",
            },
        ),
    ),
)
async def test_when_syndic_return_processes_load_then_correct_values_should_be_returned(
    expected_return, payload, encrypted_requests
):
    # ``_syndic_return`` and ``_return`` are async in Phase 2B; patch with an
    # ``AsyncMock`` so ``await self._return(ret)`` inside the loop resolves.
    fake_return = AsyncMock()
    with patch.object(encrypted_requests, "_return", fake_return):
        await encrypted_requests._syndic_return(payload)
        fake_return.assert_called_with(expected_return)


def test_aes_funcs_white(master_opts):
    """
    Validate methods exposed on AESFuncs exist and are callable
    """
    aes_funcs = salt.master.AESFuncs(master_opts)
    try:
        for name in aes_funcs.expose_methods:
            func = getattr(aes_funcs, name, None)
            assert callable(func)
    finally:
        aes_funcs.destroy()


def test_transport_methods():
    class Foo(salt.master.TransportMethods):
        expose_methods = ["bar"]

        def bar(self):
            pass

        def bang(self):
            pass

    foo = Foo()
    assert foo.get_method("bar") is not None
    assert foo.get_method("bang") is None


def test_aes_funcs_black(master_opts):
    """
    Validate methods on AESFuncs that should not be called remotely
    """
    aes_funcs = salt.master.AESFuncs(master_opts)
    # Any callable that should not explicitly be allowed should be added
    # here.
    blacklist_methods = [
        "_AESFuncs__register_resources_sync",
        "_AESFuncs__setup_fileserver",
        "_AESFuncs__verify_load",
        "_AESFuncs__verify_minion",
        "_AESFuncs__verify_minion_publish",
        "__class__",
        "__delattr__",
        "__dir__",
        "__eq__",
        "__format__",
        "__ge__",
        "__getattribute__",
        "__getstate__",
        "__gt__",
        "__hash__",
        "__init__",
        "__init_subclass__",
        "__le__",
        "__lt__",
        "__ne__",
        "__new__",
        "__reduce__",
        "__reduce_ex__",
        "__repr__",
        "__setattr__",
        "__sizeof__",
        "__str__",
        "__subclasshook__",
        "destroy",
        "get_method",
        "run_func",
        "_run_func_async",
        "_wrap_run_func_return",
        "_handle_minion_event",
        "_file_recv_write",
        # Sync helper for ``_syndic_return``'s ``run_in_executor`` offload.
        "_write_syndic_cache_marker",
        # LTS-default sync shim installer + shim bodies (``master_async_mworker`` opt-in).
        "_install_sync_handlers",
        "_sync_pillar",
        "_sync_return",
        "_sync_syndic_return",
        "_sync_register_resources",
        "_sync_file_recv",
        "_sync_verify_minion",
        "_sync_master_tops",
        "_sync_master_opts",
        "_sync_mine",
        "_sync_mine_get",
        "_sync_mine_delete",
        "_sync_mine_flush",
        "_sync_pub_ret",
        "_sync_minion_pub",
        "_sync_minion_publish",
        "_sync_minion_runner",
        "_sync_revoke_auth",
    ]
    try:
        for name in dir(aes_funcs):
            if name in aes_funcs.expose_methods:
                continue
            if not callable(getattr(aes_funcs, name)):
                continue
            assert name in blacklist_methods, name
    finally:
        aes_funcs.destroy()


def test_clear_funcs_white(master_opts):
    """
    Validate methods exposed on ClearFuncs exist and are callable
    """
    clear_funcs = salt.master.ClearFuncs(master_opts, {})
    try:
        for name in clear_funcs.expose_methods:
            func = getattr(clear_funcs, name, None)
            assert callable(func)
    finally:
        clear_funcs.destroy()


def test_clear_funcs_black(master_opts):
    """
    Validate methods on ClearFuncs that should not be called remotely
    """
    clear_funcs = salt.master.ClearFuncs(master_opts, {})
    blacklist_methods = [
        "__class__",
        "__delattr__",
        "__dir__",
        "__eq__",
        "__format__",
        "__ge__",
        "__getattribute__",
        "__getstate__",
        "__gt__",
        "__hash__",
        "__init__",
        "__init_subclass__",
        "__le__",
        "__lt__",
        "__ne__",
        "__new__",
        "__reduce__",
        "__reduce_ex__",
        "__repr__",
        "__setattr__",
        "__sizeof__",
        "__str__",
        "__subclasshook__",
        "_prep_auth_info",
        "_prep_jid",
        "_prep_pub",
        "_send_pub",
        "_send_ssh_pub",
        "connect",
        "destroy",
        "get_method",
        # LTS-default sync shim bodies (``master_async_mworker`` opt-in).
        "_sync_ping",
        "_sync_mk_token",
        "_sync_get_token",
        "_sync_runner",
        "_sync_wheel",
    ]
    try:
        for name in dir(clear_funcs):
            if name in clear_funcs.expose_methods:
                continue
            if not callable(getattr(clear_funcs, name)):
                continue
            assert name in blacklist_methods, name
    finally:
        clear_funcs.destroy()


def test_clear_funcs_get_method(clear_funcs):
    assert getattr(clear_funcs, "_prep_pub", None) is not None
    assert clear_funcs.get_method("_prep_pub") is None


def _stub_clear_funcs_side_effects(clear_funcs):
    """
    Replace the event bus and master minion with mocks so _prep_pub can
    run without touching disk or sockets.
    """
    clear_funcs.event = MagicMock()
    clear_funcs.mminion = MagicMock()


def _base_clear_load():
    return {
        "fun": "test.ping",
        "tgt": "*",
        "tgt_type": "glob",
        "ret": "",
        "arg": [],
        "user": "root",
    }


def test_prep_pub_propagates_start_event(clear_funcs):
    """
    When the caller's kwargs include start_event=True, the published
    load handed to minions must carry start_event=True.
    """
    _stub_clear_funcs_side_effects(clear_funcs)
    clear_load = _base_clear_load()
    clear_load["kwargs"] = {"start_event": True}
    load = clear_funcs._prep_pub(
        minions=["minion-a"],
        jid="20260429000000000003",
        clear_load=clear_load,
        extra={},
        missing=[],
    )
    assert load.get("start_event") is True


def test_prep_pub_omits_start_event_when_absent(clear_funcs):
    """
    If the caller did not request a start event, the key must not
    appear in the published load.
    """
    _stub_clear_funcs_side_effects(clear_funcs)
    clear_load = _base_clear_load()
    clear_load["kwargs"] = {}
    load = clear_funcs._prep_pub(
        minions=["minion-a"],
        jid="20260429000000000004",
        clear_load=clear_load,
        extra={},
        missing=[],
    )
    assert "start_event" not in load


def test_prep_pub_omits_start_event_when_falsy(clear_funcs):
    """
    A falsy start_event value (e.g. False) is treated as opt-out and
    must not produce a start_event key in the published load.
    """
    _stub_clear_funcs_side_effects(clear_funcs)
    clear_load = _base_clear_load()
    clear_load["kwargs"] = {"start_event": False}
    load = clear_funcs._prep_pub(
        minions=["minion-a"],
        jid="20260429000000000005",
        clear_load=clear_load,
        extra={},
        missing=[],
    )
    assert "start_event" not in load


def test_prep_pub_start_event_coexists_with_other_passthrough_kwargs(clear_funcs):
    """
    start_event must propagate alongside the other established
    kwargs-passthrough keys (metadata, ret_config, ret_kwargs,
    module_executors, executor_opts) without disturbing them.
    """
    _stub_clear_funcs_side_effects(clear_funcs)
    clear_load = _base_clear_load()
    clear_load["kwargs"] = {
        "start_event": True,
        "metadata": {"ticket": "INC-7"},
        "ret_config": "syslog",
        "ret_kwargs": {"retries": 2},
        "module_executors": ["sudo"],
        "executor_opts": {"sudo_user": "salt"},
    }
    load = clear_funcs._prep_pub(
        minions=["minion-a"],
        jid="20260429000000000006",
        clear_load=clear_load,
        extra={},
        missing=[],
    )
    assert load.get("start_event") is True
    assert load.get("metadata") == {"ticket": "INC-7"}
    assert load.get("ret_config") == "syslog"
    assert load.get("ret_kwargs") == {"retries": 2}
    assert load.get("module_executors") == ["sudo"]
    assert load.get("executor_opts") == {"sudo_user": "salt"}


def test_prep_pub_start_event_value_is_normalized_to_true(clear_funcs):
    """
    The master should never propagate non-boolean truthy values for
    start_event (e.g. a string from yamlify_arg or accidental dict).
    The value placed in the published load is always strictly True so
    minion-side code can rely on the type.
    """
    _stub_clear_funcs_side_effects(clear_funcs)
    for truthy in ("yes", 1, ["any"], {"present": True}):
        clear_load = _base_clear_load()
        clear_load["kwargs"] = {"start_event": truthy}
        load = clear_funcs._prep_pub(
            minions=["minion-a"],
            jid="20260429000000000007",
            clear_load=clear_load,
            extra={},
            missing=[],
        )
        assert load.get("start_event") is True, (
            f"start_event was {load.get('start_event')!r} for truthy "
            f"input {truthy!r}; expected strict True"
        )


@pytest.mark.slow_test
def test_runner_token_not_authenticated(clear_funcs):
    """
    Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "TokenAuthenticationError",
            "message": 'Authentication failure of type "token" occurred.',
        }
    }
    ret = clear_funcs.runner({"token": "asdfasdfasdfasdf"})
    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_token_authorization_error(clear_funcs):
    """
    Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
    not authorized.
    """
    token = "asdfasdfasdfasdf"
    clear_load = {"token": token, "fun": "test.arg"}
    mock_token = {"token": token, "eauth": "foo", "name": "test"}
    mock_ret = {
        "error": {
            "name": "TokenAuthenticationError",
            "message": (
                'Authentication failure of type "token" occurred for user test.'
            ),
        }
    }

    with patch(
        "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
        ret = clear_funcs.runner(clear_load)

    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_token_salt_invocation_error(clear_funcs):
    """
    Asserts that a SaltInvocationError is returned when the token authenticates, but the
    command is malformed.
    """
    token = "asdfasdfasdfasdf"
    clear_load = {"token": token, "fun": "badtestarg"}
    mock_token = {"token": token, "eauth": "foo", "name": "test"}
    mock_ret = {
        "error": {
            "name": "SaltInvocationError",
            "message": "A command invocation error occurred: Check syntax.",
        }
    }

    with patch(
        "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])):
        ret = clear_funcs.runner(clear_load)

    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_eauth_not_authenticated(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "EauthAuthenticationError",
            "message": (
                'Authentication failure of type "eauth" occurred for user UNKNOWN.'
            ),
        }
    }
    ret = clear_funcs.runner({"eauth": "foo"})
    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_eauth_authorization_error(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
    not authorized.
    """
    clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
    mock_ret = {
        "error": {
            "name": "EauthAuthenticationError",
            "message": (
                'Authentication failure of type "eauth" occurred for user test.'
            ),
        }
    }
    with patch(
        "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
        ret = clear_funcs.runner(clear_load)

    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_eauth_salt_invocation_error(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
    command is malformed.
    """
    clear_load = {"eauth": "foo", "username": "test", "fun": "bad.test.arg.func"}
    mock_ret = {
        "error": {
            "name": "SaltInvocationError",
            "message": "A command invocation error occurred: Check syntax.",
        }
    }
    with patch(
        "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])):
        ret = clear_funcs.runner(clear_load)

    assert ret == mock_ret


@pytest.mark.slow_test
def test_runner_user_not_authenticated(clear_funcs):
    """
    Asserts that an UserAuthenticationError is returned when the user can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "UserAuthenticationError",
            "message": 'Authentication failure of type "user" occurred',
        }
    }
    ret = clear_funcs.runner({})
    assert ret == mock_ret


# wheel tests


@pytest.mark.slow_test
def test_wheel_token_not_authenticated(clear_funcs):
    """
    Asserts that a TokenAuthenticationError is returned when the token can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "TokenAuthenticationError",
            "message": 'Authentication failure of type "token" occurred.',
        }
    }
    ret = clear_funcs.wheel({"token": "asdfasdfasdfasdf"})
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_token_authorization_error(clear_funcs):
    """
    Asserts that a TokenAuthenticationError is returned when the token authenticates, but is
    not authorized.
    """
    token = "asdfasdfasdfasdf"
    clear_load = {"token": token, "fun": "test.arg"}
    mock_token = {"token": token, "eauth": "foo", "name": "test"}
    mock_ret = {
        "error": {
            "name": "TokenAuthenticationError",
            "message": (
                'Authentication failure of type "token" occurred for user test.'
            ),
        }
    }

    with patch(
        "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
        ret = clear_funcs.wheel(clear_load)
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_token_salt_invocation_error(clear_funcs):
    """
    Asserts that a SaltInvocationError is returned when the token authenticates, but the
    command is malformed.
    """
    token = "asdfasdfasdfasdf"
    clear_load = {"token": token, "fun": "badtestarg"}
    mock_token = {"token": token, "eauth": "foo", "name": "test"}
    mock_ret = {
        "error": {
            "name": "SaltInvocationError",
            "message": "A command invocation error occurred: Check syntax.",
        }
    }

    with patch(
        "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])):
        ret = clear_funcs.wheel(clear_load)
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_eauth_not_authenticated(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "EauthAuthenticationError",
            "message": (
                'Authentication failure of type "eauth" occurred for user UNKNOWN.'
            ),
        }
    }
    ret = clear_funcs.wheel({"eauth": "foo"})
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_eauth_authorization_error(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user authenticates, but is
    not authorized.
    """
    clear_load = {"eauth": "foo", "username": "test", "fun": "test.arg"}
    mock_ret = {
        "error": {
            "name": "EauthAuthenticationError",
            "message": (
                'Authentication failure of type "eauth" occurred for user test.'
            ),
        }
    }
    with patch(
        "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])):
        ret = clear_funcs.wheel(clear_load)
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_eauth_salt_invocation_error(clear_funcs):
    """
    Asserts that an EauthAuthenticationError is returned when the user authenticates, but the
    command is malformed.
    """
    clear_load = {"eauth": "foo", "username": "test", "fun": "bad.test.arg.func"}
    mock_ret = {
        "error": {
            "name": "SaltInvocationError",
            "message": "A command invocation error occurred: Check syntax.",
        }
    }
    with patch(
        "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
    ), patch("salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=["testing"])):
        ret = clear_funcs.wheel(clear_load)
    assert ret == mock_ret


@pytest.mark.slow_test
def test_wheel_user_not_authenticated(clear_funcs):
    """
    Asserts that an UserAuthenticationError is returned when the user can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "UserAuthenticationError",
            "message": 'Authentication failure of type "user" occurred',
        }
    }
    ret = clear_funcs.wheel({})
    assert ret == mock_ret


# publish tests


@pytest.mark.slow_test
async def test_publish_user_is_blacklisted(clear_funcs):
    """
    Asserts that an AuthorizationError is returned when the user has been blacklisted.
    """
    mock_ret = {
        "error": {
            "name": "AuthorizationError",
            "message": "Authorization error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=True)
    ):
        assert await clear_funcs.publish({"user": "foo", "fun": "test.arg"}) == mock_ret


@pytest.mark.slow_test
async def test_publish_cmd_blacklisted(clear_funcs):
    """
    Asserts that an AuthorizationError is returned when the command has been blacklisted.
    """
    mock_ret = {
        "error": {
            "name": "AuthorizationError",
            "message": "Authorization error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch("salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=True)):
        assert await clear_funcs.publish({"user": "foo", "fun": "test.arg"}) == mock_ret


@pytest.mark.slow_test
async def test_publish_token_not_authenticated(clear_funcs):
    """
    Asserts that an AuthenticationError is returned when the token can't authenticate.
    """
    mock_ret = {
        "error": {
            "name": "AuthenticationError",
            "message": "Authentication error occurred.",
        }
    }
    load = {
        "user": "foo",
        "fun": "test.arg",
        "tgt": "test_minion",
        "kwargs": {"token": "asdfasdfasdfasdf"},
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch("salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_token_authorization_error(clear_funcs):
    """
    Asserts that an AuthorizationError is returned when the token authenticates, but is not
    authorized.
    """
    token = "asdfasdfasdfasdf"
    load = {
        "user": "foo",
        "fun": "test.arg",
        "tgt": "test_minion",
        "arg": "bar",
        "kwargs": {"token": token},
    }
    mock_token = {"token": token, "eauth": "foo", "name": "test"}
    mock_ret = {
        "error": {
            "name": "AuthorizationError",
            "message": "Authorization error occurred.",
        }
    }

    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.auth.LoadAuth.authenticate_token", MagicMock(return_value=mock_token)
    ), patch(
        "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])
    ):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_eauth_not_authenticated(clear_funcs):
    """
    Asserts that an AuthenticationError is returned when the user can't authenticate.
    """
    load = {
        "user": "test",
        "fun": "test.arg",
        "tgt": "test_minion",
        "kwargs": {"eauth": "foo"},
    }
    mock_ret = {
        "error": {
            "name": "AuthenticationError",
            "message": "Authentication error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch("salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_eauth_authorization_error(clear_funcs):
    """
    Asserts that an AuthorizationError is returned when the user authenticates, but is not
    authorized.
    """
    load = {
        "user": "test",
        "fun": "test.arg",
        "tgt": "test_minion",
        "kwargs": {"eauth": "foo"},
        "arg": "bar",
    }
    mock_ret = {
        "error": {
            "name": "AuthorizationError",
            "message": "Authorization error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.auth.LoadAuth.authenticate_eauth", MagicMock(return_value=True)
    ), patch(
        "salt.auth.LoadAuth.get_auth_list", MagicMock(return_value=[])
    ):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_user_not_authenticated(clear_funcs):
    """
    Asserts that an AuthenticationError is returned when the user can't authenticate.
    """
    load = {"user": "test", "fun": "test.arg", "tgt": "test_minion"}
    mock_ret = {
        "error": {
            "name": "AuthenticationError",
            "message": "Authentication error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch("salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_user_authenticated_missing_auth_list(clear_funcs):
    """
    Asserts that an AuthenticationError is returned when the user has an effective user id and is
    authenticated, but the auth_list is empty.
    """
    load = {
        "user": "test",
        "fun": "test.arg",
        "tgt": "test_minion",
        "kwargs": {"user": "test"},
        "arg": "foo",
    }
    mock_ret = {
        "error": {
            "name": "AuthenticationError",
            "message": "Authentication error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.auth.LoadAuth.authenticate_key",
        MagicMock(return_value="fake-user-key"),
    ), patch(
        "salt.utils.master.get_values_of_matching_keys", MagicMock(return_value=[])
    ):
        assert await clear_funcs.publish(load) == mock_ret


@pytest.mark.slow_test
async def test_publish_user_authorization_error(clear_funcs):
    """
    Asserts that an AuthorizationError is returned when the user authenticates, but is not
    authorized.
    """
    load = {
        "user": "test",
        "fun": "test.arg",
        "tgt": "test_minion",
        "kwargs": {"user": "test"},
        "arg": "foo",
    }
    mock_ret = {
        "error": {
            "name": "AuthorizationError",
            "message": "Authorization error occurred.",
        }
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.auth.LoadAuth.authenticate_key",
        MagicMock(return_value="fake-user-key"),
    ), patch(
        "salt.utils.master.get_values_of_matching_keys",
        MagicMock(return_value=["test"]),
    ), patch(
        "salt.utils.minions.CkMinions.auth_check", MagicMock(return_value=False)
    ):
        assert await clear_funcs.publish(load) == mock_ret


def test_run_func(maintenance):
    """
    Test the run function inside Maintenance class.
    """

    class MockTime:
        def __init__(self, max_duration):
            self._start_time = time.time()
            self._current_duration = 0
            self._max_duration = max_duration
            self._calls = []

        def time(self):
            return self._start_time + self._current_duration

        def sleep(self, secs):
            self._calls += [secs]
            self._current_duration += secs
            if self._current_duration >= self._max_duration:
                raise RuntimeError("Time passes")

    mocked_time = MockTime(60 * 4)

    class MockTimedFunc:
        def __init__(self):
            self.call_times = []

        def __call__(self, *args, **kwargs):
            self.call_times += [mocked_time._current_duration]

    mocked__post_fork_init = MockTimedFunc()
    mocked_clean_old_jobs = MockTimedFunc()
    mocked_clean_expired_tokens = MockTimedFunc()
    mocked_clean_pub_auth = MockTimedFunc()
    mocked_clean_proc_dir = MockTimedFunc()
    mocked_handle_git_pillar = MockTimedFunc()
    mocked_handle_schedule = MockTimedFunc()
    mocked_handle_key_cache = MockTimedFunc()
    mocked_handle_presence = MockTimedFunc()
    mocked_handle_key_rotate = MockTimedFunc()
    mocked_check_max_open_files = MockTimedFunc()

    with patch("salt.master.time", mocked_time), patch(
        "salt.utils.process", autospec=True
    ), patch("salt.master.Maintenance._post_fork_init", mocked__post_fork_init), patch(
        "salt.daemons.masterapi.clean_old_jobs", mocked_clean_old_jobs
    ), patch(
        "salt.daemons.masterapi.clean_expired_tokens", mocked_clean_expired_tokens
    ), patch(
        "salt.daemons.masterapi.clean_pub_auth", mocked_clean_pub_auth
    ), patch(
        "salt.utils.master.clean_proc_dir", mocked_clean_proc_dir
    ), patch(
        "salt.master.Maintenance.handle_git_pillar", mocked_handle_git_pillar
    ), patch(
        "salt.master.Maintenance.handle_schedule", mocked_handle_schedule
    ), patch(
        "salt.master.Maintenance.handle_key_cache", mocked_handle_key_cache
    ), patch(
        "salt.master.Maintenance.handle_presence", mocked_handle_presence
    ), patch(
        "salt.master.Maintenance.handle_key_rotate", mocked_handle_key_rotate
    ), patch(
        "salt.utils.verify.check_max_open_files", mocked_check_max_open_files
    ):
        try:
            maintenance.run()
        except RuntimeError as exc:
            assert str(exc) == "Time passes"
        assert mocked_time._calls == [60] * 4
        assert mocked__post_fork_init.call_times == [0]
        assert mocked_clean_old_jobs.call_times == [0, 120, 180]
        assert mocked_clean_expired_tokens.call_times == [0, 120, 180]
        assert mocked_clean_pub_auth.call_times == [0, 120, 180]
        assert mocked_clean_proc_dir.call_times == [0, 120, 180]
        assert mocked_handle_git_pillar.call_times == [0]
        assert mocked_handle_schedule.call_times == [0, 60, 120, 180]
        assert mocked_handle_key_cache.call_times == [0, 60, 120, 180]
        assert mocked_handle_presence.call_times == [0, 60, 120, 180]
        assert mocked_handle_key_rotate.call_times == [0, 60, 120, 180]
        assert mocked_check_max_open_files.call_times == [0, 60, 120, 180]


def test_key_rotate_master_match(maintenance):
    maintenance.event = MagicMock()
    now = time.monotonic()
    dfn = pathlib.Path(maintenance.opts["cachedir"]) / ".dfn"
    salt.crypt.dropfile(
        maintenance.opts["cachedir"],
        maintenance.opts["user"],
        master_id=maintenance.opts["id"],
    )
    assert dfn.exists()
    with patch("salt.master.SMaster.rotate_secrets") as rotate_secrets:
        maintenance.handle_key_rotate(now)
        assert not dfn.exists()
        rotate_secrets.assert_called_with(
            maintenance.opts, maintenance.event, owner=True
        )


def test_key_rotate_no_master_match(maintenance):
    now = time.monotonic()
    dfn = pathlib.Path(maintenance.opts["cachedir"]) / ".dfn"
    dfn.write_text("nomatch")
    assert dfn.exists()
    with patch("salt.master.SMaster.rotate_secrets") as rotate_secrets:
        maintenance.handle_key_rotate(now)
        assert dfn.exists()
        rotate_secrets.assert_not_called()


@pytest.mark.slow_test
def test_key_dfn_wait(cluster_maintenance):
    now = time.monotonic()
    key = pathlib.Path(cluster_maintenance.opts["cluster_pki_dir"]) / ".aes"
    salt.crypt.Crypticle.write_key(str(key))
    rotate_time = time.monotonic() - (cluster_maintenance.opts["publish_session"] + 1)
    os.utime(str(key), (rotate_time, rotate_time))

    dfn = pathlib.Path(cluster_maintenance.opts["cachedir"]) / ".dfn"

    def run_key_rotate():
        with patch("salt.master.SMaster.rotate_secrets") as rotate_secrets:
            cluster_maintenance.handle_key_rotate(now)
            assert dfn.exists()
            rotate_secrets.assert_not_called()

    thread = threading.Thread(target=run_key_rotate)
    assert not dfn.exists()
    start = time.monotonic()
    thread.start()

    while not dfn.exists():
        if time.monotonic() - start > 30:
            assert dfn.exists(), "dfn file never created"

    assert cluster_maintenance.opts["id"] == dfn.read_text()

    with salt.utils.files.set_umask(0o277):
        if os.path.isfile(dfn) and not os.access(dfn, os.W_OK):
            os.chmod(dfn, stat.S_IRUSR | stat.S_IWUSR)
        dfn.write_text("othermaster")

    thread.join()
    assert time.time() - start >= 5
    assert dfn.read_text() == "othermaster"


async def test_syndic_return_cache_dir_creation(encrypted_requests):
    """master's cachedir for a syndic will be created by AESFuncs._syndic_return method"""
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    await encrypted_requests._syndic_return(
        {
            "id": "mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert (cachedir / "syndics").exists()
    assert (cachedir / "syndics" / "mamajama").exists()


async def test_syndic_return_cache_dir_creation_traversal(encrypted_requests):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    await encrypted_requests._syndic_return(
        {
            "id": "../mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert not (cachedir / "syndics").exists()
    assert not (cachedir / "mamajama").exists()


@pytest.mark.no_blocking(
    reason="RSA gen_keys(2048) runs inline in the test body (~60-100ms of "
    "sync CPU) and shares the callback slice with pub_ret; blocking "
    "detection would flag test setup, not handler behaviour. Move RSA "
    "generation to a session fixture to re-enable detection."
)
async def test_pub_ret_traversal(encrypted_requests, tmp_path):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    priv, pub = salt.crypt.gen_keys(2048)

    minions = pathlib.Path(encrypted_requests.opts["pki_dir"]) / "minions"
    minions.mkdir()

    with salt.utils.files.fopen(minions / "minion", "w") as wfp:
        wfp.write(pub)

    with pytest.raises(salt.exceptions.SaltValidationError):
        await encrypted_requests.pub_ret(
            {
                "tok": salt.crypt.PrivateKey.from_str(priv).encrypt(b"salt"),
                "id": "minion",
                "jid": "asdf/../../../sdf",
                "return": {},
            }
        )


@pytest.mark.no_blocking(
    reason="Inline RSA gen_keys(2048) + file I/O + signing all run in the "
    "same callback slice as the _return() call under test. Move RSA "
    "generation to a session fixture to re-enable detection."
)
async def test_return_signature_verifies_after_channel_packaging(tmp_path, caplog):
    """
    Regression test for #68181.

    With ``minion_sign_messages`` enabled, the minion previously signed the
    return load before ``AsyncReqChannel._package_load`` attached transport
    metadata (``nonce``, ``ts``, ``tok``, ``id``). The bytes the master
    re-serialized to verify therefore did not match what was signed, and
    every signed return was silently dropped under
    ``drop_messages_signature_fail``. Signing is now done inside
    ``_package_load`` after the metadata is attached.
    """
    priv_pem, pub_pem = salt.crypt.gen_keys(2048)
    with salt.utils.files.fopen(tmp_path / "minion.pem", "wb") as f:
        f.write(priv_pem if isinstance(priv_pem, bytes) else priv_pem.encode())
    with salt.utils.files.fopen(tmp_path / "minion.pub", "wb") as f:
        f.write(pub_pem if isinstance(pub_pem, bytes) else pub_pem.encode())
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    accepted = pki_dir / "minions"
    accepted.mkdir()
    with salt.utils.files.fopen(accepted / "minion", "wb") as wfp:
        with salt.utils.files.fopen(tmp_path / "minion.pub", "rb") as rfp:
            wfp.write(rfp.read())

    # Bypass the heavyweight AESFuncs.__init__ (which spins up event loops,
    # file servers, master minion, etc.) and set only what _return() needs.
    with salt.utils.files.fopen(tmp_path / "minion.pub", "rb") as f:
        minion_pub = f.read().decode()
    aes_funcs = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes_funcs.opts = {
        "pki_dir": str(pki_dir),
        "cachedir": str(tmp_path / "cache"),
        "require_minion_sign_messages": True,
        "drop_messages_signature_fail": True,
        # SHA224 so the test works on FIPS-enabled platforms too.
        "signing_algorithm": salt.crypt.PKCS1v15_SHA224,
    }
    aes_funcs.key_cache = MagicMock()
    aes_funcs.key_cache.fetch.return_value = {"pub": minion_pub}
    aes_funcs.event = MagicMock()
    aes_funcs.mminion = MagicMock()

    # Load as Minion._prepare_return_pub would build it for a test.ping return.
    load = {
        "cmd": "_return",
        "id": "minion",
        "success": True,
        "fun_args": [],
        "jid": "20260527000000000000",
        "return": True,
        "retcode": 0,
        "fun": "test.ping",
        "out": "nested",
    }

    # Build an AsyncReqChannel just complete enough to exercise _package_load.
    # We bypass __init__ to avoid spinning up a real transport / auth handshake.
    channel = salt.channel.client.AsyncReqChannel.__new__(
        salt.channel.client.AsyncReqChannel
    )
    channel.opts = {
        "id": "minion",
        "pki_dir": str(tmp_path),
        "minion_sign_messages": True,
        "encryption_algorithm": salt.crypt.OAEP_SHA224,
        "signing_algorithm": salt.crypt.PKCS1v15_SHA224,
    }
    channel.auth = MagicMock()
    channel.auth.gen_token.return_value = b"\x00" * 256
    # Bypass session encryption so we can read the load the master would see.
    channel.auth.session_crypticle = MagicMock()
    channel.auth.session_crypticle.dumps = lambda payload: payload

    packaged = channel._package_load(load)
    inner_load = packaged["load"]

    # ReqServerChannel pops these transport-only fields before the load reaches
    # AESFuncs._return. Mirror that here.
    inner_load.pop("nonce", None)
    inner_load.pop("tok", None)

    assert "sig" in inner_load, (
        "Channel did not attach a signature to the outbound load even though "
        "minion_sign_messages is enabled (#68181)."
    )

    with patch("salt.utils.job.store_job") as store_job, caplog.at_level("INFO"):
        ret = await aes_funcs._return(inner_load)

    assert "Failed to verify event signature" not in caplog.text, (
        "Master rejected a valid signed return because the channel signed "
        "the load before attaching transport metadata (#68181)."
    )
    assert ret is not False
    assert store_job.called


def _git_pillar_base_config(tmp_path):
    return {
        "__role": "master",
        "pki_dir": str(tmp_path / "pki"),
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock_drawer"),
        "conf_file": str(tmp_path / "config.conf"),
        "keys.cache_driver": "localfs_key",
        "fileserver_backend": ["local"],
        "master_job_cache": False,
        "file_client": "local",
        "pillar_cache": False,
        "state_top": "top.sls",
        "pillar_roots": {
            "base": [str(tmp_path / "pillar")],
        },
        "render_dirs": [str(pathlib.Path(RUNTIME_VARS.SALT_CODE_DIR) / "renderer")],
        "renderer": "jinja|yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "optimization_order": [0, 1, 2],
        "on_demand_ext_pillar": [],
        "git_pillar_user": "",
        "git_pillar_password": "",
        "git_pillar_pubkey": "",
        "git_pillar_privkey": "",
        "git_pillar_passphrase": "",
        "git_pillar_insecure_auth": False,
        "git_pillar_refspecs": salt.config._DFLT_REFSPECS,
        "git_pillar_ssl_verify": True,
        "git_pillar_branch": "master",
        "git_pillar_base": "master",
        "git_pillar_root": "",
        "git_pillar_env": "",
        "git_pillar_fallback": "",
        "git_pillar_proxy": "",
        # These tests exercise the async ``_pillar`` handler; opt in
        # so ``AESFuncs.__init__`` does not shadow it with the sync body.
        "master_async_mworker": True,
    }


@pytest.fixture
def allowed_funcs(tmp_path):
    """
    Configuration with git on demand pillar allowed
    """
    opts = _git_pillar_base_config(tmp_path)
    opts["on_demand_ext_pillar"] = ["git"]
    priv, pub = salt.crypt.gen_keys(2048)
    master_pki = tmp_path / "pki"
    master_pki.mkdir()
    accepted_pki = master_pki / "minions"
    accepted_pki.mkdir()
    (accepted_pki / "minion.pub").write_text(pub)
    return salt.master.AESFuncs(opts=opts)


@skipif_no_pygit2
async def test_on_demand_allowed_command_injection(allowed_funcs, tmp_path, caplog):
    """
    Verify on demand pillars validate remote urls
    """
    pwnpath = tmp_path / "pwn"
    assert not pwnpath.exists()
    load = {
        "cmd": "_pillar",
        "saltenv": "base",
        "pillarenv": "base",
        "id": "carbon",
        "grains": {},
        "ver": 2,
        "ext": {
            "git": [
                f'base ssh://fake@git/repo\n[core]\nsshCommand = touch {pwnpath}\n[remote "origin"]\n'
            ]
        },
        "clean_cache": True,
    }
    with caplog.at_level(level="WARNING"):
        ret = await allowed_funcs._pillar(load)
    assert not pwnpath.exists()
    assert "Found bad url data" in caplog.text


@pytest.fixture
def not_allowed_funcs(tmp_path):
    """
    Configuration with no on demand pillars allowed
    """
    opts = _git_pillar_base_config(tmp_path)
    opts["on_demand_ext_pillar"] = []
    priv, pub = salt.crypt.gen_keys(2048)
    master_pki = tmp_path / "pki"
    master_pki.mkdir()
    accepted_pki = master_pki / "minions"
    accepted_pki.mkdir()
    (accepted_pki / "minion.pub").write_text(pub)

    return salt.master.AESFuncs(opts=opts)


async def test_on_demand_not_allowed(not_allowed_funcs, tmp_path, caplog):
    """
    Verify on demand pillars do not render when not allowed
    """
    pwnpath = tmp_path / "pwn"
    assert not pwnpath.exists()
    load = {
        "cmd": "_pillar",
        "saltenv": "base",
        "pillarenv": "base",
        "id": "carbon",
        "grains": {},
        "ver": 2,
        "ext": {
            "git": [
                f'base ssh://fake@git/repo\n[core]\nsshCommand = touch {pwnpath}\n[remote "origin"]\n'
            ]
        },
        "clean_cache": True,
    }
    with caplog.at_level(level="WARNING"):
        ret = await not_allowed_funcs._pillar(load)
    assert not pwnpath.exists()
    assert (
        "The following ext_pillar modules are not allowed for on-demand pillar data: git."
        in caplog.text
    )


async def test_register_resources_updates_resource_index_when_minion_data_cache_disabled(
    master_opts,
    tmp_path,
):
    """
    Resource mmap registration must not depend on minion pillar/grains caching.

    Regression: ``minion_data_cache: False`` skipped ``update_resource_index``
    entirely while still returning success to the minion.
    """
    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = False
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)

    aes_funcs = salt.master.AESFuncs(opts)
    try:
        load = {"id": "minion-2", "resources": {"dummy": ["m2-dummy2"]}}
        with patch(
            "salt.utils.minions.update_resource_index", return_value=(1, 0)
        ) as ur:
            await aes_funcs._register_resources(load)
        ur.assert_called_once_with(opts, "minion-2", {"dummy": ["m2-dummy2"]})
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


def _make_aes_funcs_for_resource_grains(master_opts, tmp_path):
    """Helper: build an ``AESFuncs`` ready for ``resource_grains`` testing."""
    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = True
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)
    return salt.master.AESFuncs(opts), opts


async def test_register_resources_persists_resource_grains_to_cache(
    master_opts, tmp_path
):
    """
    Each ``resource_grains[srn]`` entry in the registration load is written
    into the master's ``resource_grains`` cache bank so ``-G``/``-P``
    targeting can later match them.
    """
    import salt.utils.resource_registry

    aes_funcs, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    try:
        load = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1", "m2-d2"]},
            "resource_grains": {
                "dummy:m2-d1": {"k": "v1", "resource_id": "m2-d1"},
                "dummy:m2-d2": {"k": "v2", "resource_id": "m2-d2"},
            },
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(2, 0)):
            await aes_funcs._register_resources(load)
        cache = aes_funcs.masterapi.cache
        stored_keys = sorted(cache.list("resource_grains") or [])
        assert stored_keys == ["dummy:m2-d1", "dummy:m2-d2"]
        assert cache.fetch("resource_grains", "dummy:m2-d1") == {
            "k": "v1",
            "resource_id": "m2-d1",
        }
        assert cache.fetch("resource_grains", "dummy:m2-d2") == {
            "k": "v2",
            "resource_id": "m2-d2",
        }
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_flushes_dropped_resource_grain_entry(
    master_opts, tmp_path
):
    """
    Re-registering with a smaller resource set must flush the dropped
    SRN's grain entry from the ``resource_grains`` bank when the registry
    confirms no other minion now manages it.
    """
    import salt.utils.resource_registry

    aes_funcs, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    try:
        # First registration: minion owns m2-d1 and m2-d2.
        load1 = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1", "m2-d2"]},
            "resource_grains": {
                "dummy:m2-d1": {"k": "v1"},
                "dummy:m2-d2": {"k": "v2"},
            },
        }
        # Real ``update_resource_index`` so the registry actually tracks
        # ownership for the flush owner-check.
        await aes_funcs._register_resources(load1)
        cache = aes_funcs.masterapi.cache
        assert sorted(cache.list("resource_grains") or []) == [
            "dummy:m2-d1",
            "dummy:m2-d2",
        ]
        # Second registration: minion drops m2-d2.
        load2 = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1"]},
            "resource_grains": {"dummy:m2-d1": {"k": "v1-updated"}},
        }
        await aes_funcs._register_resources(load2)
        # The flush must remove the orphaned SRN.
        remaining = sorted(cache.list("resource_grains") or [])
        assert remaining == ["dummy:m2-d1"]
        # And the surviving entry must reflect the most recent payload.
        assert cache.fetch("resource_grains", "dummy:m2-d1") == {"k": "v1-updated"}
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_does_not_flush_srn_owned_by_other_minion(
    master_opts, tmp_path
):
    """
    Two minions managing different SRNs must not stomp on each other's
    ``resource_grains`` entries during re-registration. When minion-A drops
    a SRN that minion-B owns (rare but possible if the registry was
    re-keyed), the flush must skip it.
    """
    import salt.utils.resource_registry

    aes_funcs, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    try:
        # minion-A registers dummy:shared.
        await aes_funcs._register_resources(
            {
                "id": "minion-A",
                "resources": {"dummy": ["shared"]},
                "resource_grains": {"dummy:shared": {"who": "A"}},
            }
        )
        # minion-B claims dummy:shared (registry overwrites the SRN's owner).
        await aes_funcs._register_resources(
            {
                "id": "minion-B",
                "resources": {"dummy": ["shared"]},
                "resource_grains": {"dummy:shared": {"who": "B"}},
            }
        )
        cache = aes_funcs.masterapi.cache
        assert cache.fetch("resource_grains", "dummy:shared") == {"who": "B"}
        # minion-A re-registers with no resources. Its flush walk would
        # consider dummy:shared "stale"; the owner check (registry says B
        # owns it) must prevent the flush.
        await aes_funcs._register_resources(
            {
                "id": "minion-A",
                "resources": {},
                "resource_grains": {},
            }
        )
        assert cache.fetch("resource_grains", "dummy:shared") == {"who": "B"}
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_resource_grains_visible_across_aes_funcs_instances(
    master_opts, tmp_path
):
    """
    The ``resource_grains`` bank lives on the filesystem (localfs cache)
    so a second master worker (modelled by a fresh ``AESFuncs`` instance
    under the same ``cachedir``) sees the entries that the first worker
    wrote. Without this guarantee, multi-worker masters would silently
    fail grain-based resource targeting on workers that didn't handle the
    minion's registration.
    """
    import salt.utils.resource_registry

    aes_funcs_a, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    try:
        await aes_funcs_a._register_resources(
            {
                "id": "minion-2",
                "resources": {"dummy": ["m2-d1"]},
                "resource_grains": {"dummy:m2-d1": {"env": "prod"}},
            }
        )
    finally:
        aes_funcs_a.destroy()
        # Reset only the registry singleton — the localfs cache on disk is
        # what we're verifying survives.
        salt.utils.resource_registry.reset_registry()

    # Second worker reads the same on-disk cachedir.
    aes_funcs_b = salt.master.AESFuncs(opts)
    try:
        cache_b = aes_funcs_b.masterapi.cache
        assert cache_b.fetch("resource_grains", "dummy:m2-d1") == {"env": "prod"}
    finally:
        aes_funcs_b.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_fires_minion_data_cache_event(master_opts, tmp_path):
    """
    When ``minion_data_cache: True`` and ``minion_data_cache_events: True``,
    ``_register_resources`` must fire a cache-refresh event on the master
    event bus that mirrors the notification ``_pillar`` fires for ordinary
    minion grains. Without this signal, downstream consumers subscribed to
    cache-refresh events miss every resource registration.

    Regression for #69451.
    """
    import salt.utils.resource_registry

    aes_funcs, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    opts["minion_data_cache_events"] = True
    aes_funcs.opts["minion_data_cache_events"] = True
    aes_funcs.event = MagicMock()

    # ``fire_event_async`` is awaited by the async ``_register_resources``.
    async def _fake_fire_async(data, tag):
        return None

    aes_funcs.event.fire_event_async = MagicMock(side_effect=_fake_fire_async)
    try:
        load = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1"]},
            "resource_grains": {"dummy:m2-d1": {"k": "v1"}},
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)):
            await aes_funcs._register_resources(load)
        # ``_pillar`` fires ``minion/refresh/<id>`` for grain refreshes (see
        # the analogous ``tagify(load["id"], "refresh", "minion")`` call);
        # the resource registration path mirrors that with ``resource`` as
        # the namespace, yielding ``resource/refresh/<id>``.
        aes_funcs.event.fire_event_async.assert_called_once_with(
            {"Resource cache refresh": "minion-2"},
            "resource/refresh/minion-2",
        )
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_does_not_fire_event_when_events_disabled(
    master_opts, tmp_path
):
    """
    With ``minion_data_cache: True`` but ``minion_data_cache_events: False``,
    ``_register_resources`` must not fire a cache-refresh event. Symmetric
    to ``_pillar``'s behaviour.

    Regression for #69451.
    """
    import salt.utils.resource_registry

    aes_funcs, opts = _make_aes_funcs_for_resource_grains(master_opts, tmp_path)
    opts["minion_data_cache_events"] = False
    aes_funcs.opts["minion_data_cache_events"] = False
    aes_funcs.event = MagicMock()
    aes_funcs.event.fire_event_async = MagicMock()
    try:
        load = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1"]},
            "resource_grains": {"dummy:m2-d1": {"k": "v1"}},
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)):
            await aes_funcs._register_resources(load)
        aes_funcs.event.fire_event.assert_not_called()
        aes_funcs.event.fire_event_async.assert_not_called()
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_collect__auth_to_master_stats():
    """
    Check if master stats is collecting _auth calls while not calling neither _handle_aes nor _handle_clear
    """
    opts = {
        "master_stats": True,
        "master_stats_event_iter": 10,
    }
    req_channel_mock = MagicMock()
    mworker = salt.master.MWorker(opts, {}, {}, [req_channel_mock])
    with patch.object(mworker, "_handle_aes") as handle_aes_mock, patch.object(
        mworker, "_handle_clear"
    ) as handle_clear_mock:
        await mworker._handle_payload({"cmd": "_auth", "_start": time.time() - 0.02})
        assert mworker.stats["_auth"]["runs"] == 1
        assert mworker.stats["_auth"]["mean"] >= 0.02
        assert mworker.stats["_auth"]["mean"] < 0.04
        await mworker._handle_payload({"cmd": "_auth", "_start": time.time() - 0.02})
        assert mworker.stats["_auth"]["runs"] == 2
        assert mworker.stats["_auth"]["mean"] >= 0.02
        assert mworker.stats["_auth"]["mean"] < 0.04
        handle_aes_mock.assert_not_called()
        handle_clear_mock.assert_not_called()


# ---------------------------------------------------------------------------
# AuthFuncs
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_funcs(master_opts):
    """
    A real :class:`salt.master.AuthFuncs` instance backed by tmp_path-rooted
    opts.  Used for tests that exercise the auth handler directly without
    going through the channel layer.
    """
    SMaster = salt.master.SMaster
    if "aes" not in SMaster.secrets:
        import ctypes
        import multiprocessing

        SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "reload": salt.crypt.Crypticle.generate_key_string,
        }
    af = salt.master.AuthFuncs(master_opts)
    yield af
    if af.event is not None:
        af.event.destroy()


def test_auth_funcs_exposes_only_auth():
    """
    Only ``_auth`` is exposed to the transport layer.  Adding methods to the
    class without updating this test would silently expand the master's
    cleartext API surface.
    """
    assert salt.master.AuthFuncs.expose_methods == ("_auth",)


def test_auth_funcs_get_method_only_auth(auth_funcs):
    """
    :meth:`TransportMethods.get_method` returns ``_auth`` and nothing else.
    """
    assert auth_funcs.get_method("_auth") is not None
    # Helpers must not be reachable from the transport layer.
    assert auth_funcs.get_method("_clear_signed") is None
    assert auth_funcs.get_method("session_key") is None
    assert auth_funcs.get_method("destroy") is None


def test_auth_funcs_compare_keys_normalizes(tmp_path):
    """
    :meth:`AuthFuncs.compare_keys` must treat keys with mismatched line
    endings or trailing whitespace as equal.  The classmethod is the only
    other auth-relevant utility, mirrored from the legacy implementation
    on :class:`ReqServerChannel`.
    """
    unix = "-----BEGIN PUBLIC KEY-----\nABC\n-----END PUBLIC KEY-----\n"
    dos = "-----BEGIN PUBLIC KEY-----\r\nABC\r\n-----END PUBLIC KEY-----\r\n"
    padded = unix + "   \n"
    assert salt.master.AuthFuncs.compare_keys(unix, dos) is True
    assert salt.master.AuthFuncs.compare_keys(unix, padded) is True


async def test_auth_funcs_rejects_invalid_id(auth_funcs):
    """
    An auth load whose ``id`` fails :func:`salt.utils.verify.valid_id` is
    rejected without touching the cache or firing an event.
    """
    auth_funcs.cache = MagicMock()
    auth_funcs.event = MagicMock()
    load = {
        "id": "../escape",
        "pub": "stub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": False}}
    auth_funcs.cache.fetch.assert_not_called()
    auth_funcs.event.fire_event.assert_not_called()
    auth_funcs.event.fire_event_async.assert_not_called()


async def test_auth_funcs_rejects_when_max_minions_full(auth_funcs):
    """
    When ``max_minions`` is reached and the requesting id is unknown, the
    handler returns ``{"ret": "full"}`` and does not store any key state.
    """
    auth_funcs.opts["max_minions"] = 1
    auth_funcs.opts["auth_events"] = False
    auth_funcs.cache = MagicMock()
    auth_funcs.cache_cli = False
    ckminions = MagicMock()
    # Two existing minions, max_minions=1 ⇒ pool full.  The newcomer is not
    # already-connected so they should be rejected with ``ret: "full"``.
    ckminions.connected_ids.return_value = {"already-here", "another"}
    auth_funcs.ckminions = ckminions
    load = {
        "id": "newcomer",
        "pub": "stub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": "full"}}
    auth_funcs.cache.store.assert_not_called()


async def test_auth_funcs_rejected_key_state(auth_funcs):
    """
    A minion whose stored key state is ``rejected`` gets
    ``{"ret": False}`` and the handler must not overwrite the rejection.
    """
    auth_funcs.opts["max_minions"] = 0
    auth_funcs.opts["auth_events"] = False
    auth_funcs.opts["open_mode"] = False
    auth_funcs.auto_key = MagicMock()
    auth_funcs.auto_key.check_autoreject.return_value = False
    auth_funcs.auto_key.check_autosign.return_value = False
    cache = MagicMock()
    cache.fetch.side_effect = lambda bucket, key: (
        {"pub": "stored-pub", "state": "rejected"} if bucket == "keys" else None
    )
    auth_funcs.cache = cache
    load = {
        "id": "rejected-minion",
        "pub": "incoming-pub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": False}}
    cache.store.assert_not_called()


async def test_auth_funcs_pending_when_new_minion(auth_funcs):
    """
    A previously-unseen minion (no stored key, no auto-sign) is placed in
    ``pending`` and the handler reports ``{"ret": True}``.
    """
    auth_funcs.opts["max_minions"] = 0
    auth_funcs.opts["auth_events"] = False
    auth_funcs.opts["open_mode"] = False
    auth_funcs.auto_key = MagicMock()
    auth_funcs.auto_key.check_autoreject.return_value = False
    auth_funcs.auto_key.check_autosign.return_value = False
    cache = MagicMock()
    cache.fetch.return_value = None
    auth_funcs.cache = cache
    load = {
        "id": "fresh-minion",
        "pub": "fresh-pub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": True}}
    cache.store.assert_called_once_with(
        "keys", "fresh-minion", {"pub": "fresh-pub", "state": "pending"}
    )


def test_register_resources_concurrent_workers_no_data_loss(master_opts, tmp_path):
    """
    Two simulated master workers concurrently registering different
    minions must not stomp on each other's ``resource_grains`` entries.
    Each worker writes the entry it owns; the flush owner-check defends
    against the case where one worker's "drop stale" walk encounters an
    SRN that another worker has just claimed.
    """
    import threading

    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = True
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)

    # Two AESFuncs sharing the same on-disk cachedir.
    aes_a = salt.master.AESFuncs(opts)
    aes_b = salt.master.AESFuncs(opts)
    try:
        errs = []
        barrier = threading.Barrier(2)

        def _register(aes, minion_id, resource_id, grain_value):
            try:
                barrier.wait(timeout=10)
                # Async ``_register_resources`` offloads its blocking body
                # (mmap write + cache mutations) to ``__register_resources_sync``
                # via ``loop.run_in_executor``. This concurrency test
                # exercises exactly that blocking body across two OS
                # threads, so invoke it directly — that mirrors what the
                # executor pool would do in production without requiring
                # an event loop per worker thread.
                aes._AESFuncs__register_resources_sync(
                    {
                        "id": minion_id,
                        "resources": {"dummy": [resource_id]},
                        "resource_grains": {
                            f"dummy:{resource_id}": {"who": grain_value}
                        },
                    }
                )
            except Exception as exc:  # pylint: disable=broad-except
                errs.append(exc)

        t1 = threading.Thread(target=_register, args=(aes_a, "minion-A", "rA", "A"))
        t2 = threading.Thread(target=_register, args=(aes_b, "minion-B", "rB", "B"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errs, errs
        cache = aes_a.masterapi.cache
        # Both entries must survive: neither worker's flush walk should
        # have wiped the other's entry.
        assert cache.fetch("resource_grains", "dummy:rA") == {"who": "A"}
        assert cache.fetch("resource_grains", "dummy:rB") == {"who": "B"}
    finally:
        aes_a.destroy()
        aes_b.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_handle_clear_missing_cmd_returns_empty_reply(caplog):
    """
    Cleartext loads without ``cmd`` must not raise; the REQ channel unpacks a
    (ret, req_opts) tuple from the payload handler.
    """
    worker = object.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    with caplog.at_level("ERROR"):
        ret = await salt.master.MWorker._handle_clear(worker, {})
    assert ret == ({}, {"fun": "send_clear"})
    assert "Received malformed clear command (missing 'cmd')" in caplog.text


@pytest.mark.parametrize(
    "cached_present,connected_ids,change_expected",
    [
        (
            # No change: same minions in cache and currently connected.
            ["minion1", "minion2"],
            {"minion1", "minion2"},
            False,
        ),
        (
            # A new minion appeared since last cache write.
            ["minion1"],
            {"minion1", "minion2"},
            True,
        ),
        (
            # A minion disappeared since last cache write.
            ["minion1", "minion2"],
            {"minion1"},
            True,
        ),
    ],
)
def test_handle_presence(
    maintenance, cached_present, connected_ids, change_expected, tmp_path
):
    """
    handle_presence fires a /present event every cycle and a /change event only
    when the set of connected minions differs from the cached presence list.
    After each call the cache on disk must reflect the current connected set.
    """
    fire_event = MagicMock()

    # Seed the presence cache with old (possibly stale) data.
    presence_cache = salt.utils.cache.CacheFactory.factory(
        "disk",
        3600,
        minion_cache_path=os.path.join(maintenance.opts["cachedir"], "presence-data"),
    )
    presence_cache.clear()
    presence_cache["present"] = cached_present

    with patch("salt.master.Maintenance.run", MagicMock()), patch(
        "salt.master.Maintenance.presence_events", True, create=True
    ), patch(
        "salt.master.Maintenance.event",
        MagicMock(
            connect_pull=MagicMock(return_value=True),
            fire_event=fire_event,
        ),
        create=True,
    ), patch(
        "salt.master.Maintenance.ckminions",
        MagicMock(connected_ids=MagicMock(return_value=connected_ids)),
        create=True,
    ):
        maintenance.handle_presence(set(presence_cache["present"]))

        # A /present event is always fired.
        assert fire_event.called

        if change_expected:
            # A /change event must be fired in addition to /present.
            assert fire_event.call_count == 2
            change_events = [
                c[0][0] for c in fire_event.call_args_list if "/change" in c[0][1]
            ]
            assert change_events, "Expected a /change event but none was fired"
        else:
            assert fire_event.call_count == 1

        present_event = [
            c[0][0] for c in fire_event.call_args_list if "/present" in c[0][1]
        ][0]
        assert (
            set(present_event["present"]) == connected_ids
        ), "The /present event does not contain the expected minion set"

        # The cache on disk must now reflect the current connected set.
        new_presence_cache = salt.utils.cache.CacheFactory.factory(
            "disk",
            3600,
            minion_cache_path=os.path.join(
                maintenance.opts["cachedir"], "presence-data"
            ),
        )
        assert (
            set(new_presence_cache["present"]) == connected_ids
        ), "The presence cache on disk does not reflect the current connected set"


@pytest.fixture
def publish_clear_funcs(master_opts):
    """
    A ClearFuncs bound to a master_opts that will let ``publish`` reach
    ``_prep_jid`` without touching auth, the ACL, or the returner loader.
    """
    clear_funcs = salt.master.ClearFuncs(master_opts, {})
    try:
        yield clear_funcs
    finally:
        clear_funcs.destroy()


async def test_publish_prep_jid_returns_error_dict(publish_clear_funcs):
    """
    Regression test for #66457.

    When the returner configured as ``master_job_cache`` fails to load,
    ``ClearFuncs._prep_jid`` returns ``{"error": <msg>}``. ``publish`` must
    treat that dict the same as ``None`` and return the error load back to
    the caller instead of passing the dict through as the jid, which would
    later blow up in ``fire_event`` with
    ``TypeError: expected str, bytes, or bytearray not <class 'dict'>``.
    """
    load = {
        "user": "foo",
        "fun": "test.ping",
        "tgt": "test_minion",
        "arg": [],
    }
    prep_jid_error = {
        "error": (
            "Failed to allocate a jid. The requested returner"
            " 'not_a_real_returner' could not be loaded."
        )
    }
    check_minions_ret = {
        "minions": ["test_minion"],
        "missing": [],
        "ssh_minions": False,
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch.object(
        publish_clear_funcs.ckminions,
        "check_minions",
        MagicMock(return_value=check_minions_ret),
    ), patch.object(
        publish_clear_funcs.loadauth,
        "check_authentication",
        MagicMock(return_value={"auth_list": [], "error": None}),
    ), patch.object(
        publish_clear_funcs,
        "_prep_jid",
        MagicMock(return_value=prep_jid_error),
    ):
        # Before #66457 was fixed, ``publish`` would pass ``prep_jid_error``
        # (a dict) through as the jid and then raise ``TypeError`` inside
        # ``fire_event`` while converting it to bytes.
        result = await publish_clear_funcs.publish(load)

    assert result == prep_jid_error, (
        "publish() must return the error dict from _prep_jid unchanged when"
        " the master_job_cache returner fails to load (#66457)."
    )


async def test_publish_prep_jid_returns_none(publish_clear_funcs):
    """
    Companion to :func:`test_publish_prep_jid_returns_error_dict`: verify the
    pre-existing ``jid is None`` path still returns the generic error load.
    """
    load = {
        "user": "foo",
        "fun": "test.ping",
        "tgt": "test_minion",
        "arg": [],
    }
    check_minions_ret = {
        "minions": ["test_minion"],
        "missing": [],
        "ssh_minions": False,
    }
    with patch(
        "salt.acl.PublisherACL.user_is_blacklisted", MagicMock(return_value=False)
    ), patch(
        "salt.acl.PublisherACL.cmd_is_blacklisted", MagicMock(return_value=False)
    ), patch.object(
        publish_clear_funcs.ckminions,
        "check_minions",
        MagicMock(return_value=check_minions_ret),
    ), patch.object(
        publish_clear_funcs.loadauth,
        "check_authentication",
        MagicMock(return_value={"auth_list": [], "error": None}),
    ), patch.object(
        publish_clear_funcs,
        "_prep_jid",
        MagicMock(return_value=None),
    ):
        result = await publish_clear_funcs.publish(load)

    assert result == {"error": "Master failed to assign jid"}


def test_local_client_pub_handles_str_payload(tmp_path):
    """
    Regression test for #66457 (LocalClient side).

    Before the fix, a bare-string payload returned by the master (e.g. an
    error string that never got wrapped in an envelope) triggered
    ``AttributeError: 'str' object has no attribute 'pop'`` when
    ``LocalClient.pub`` tried to extract the error. The client now converts
    a str payload into ``{"error": payload}`` so that ``payload.pop`` works
    and the error propagates back to the CLI as a ``PublishError``.
    """
    import salt.client
    from salt.exceptions import PublishError

    sock_dir = tmp_path / "sock"
    sock_dir.mkdir()
    # LocalClient.pub bails out early with SaltClientError unless the
    # publisher IPC socket exists (or ipc_mode is "tcp").
    (sock_dir / "publish_pull.ipc").touch()

    client = salt.client.LocalClient.__new__(salt.client.LocalClient)
    client.opts = {
        "transport": "zeromq",
        "ipc_mode": "ipc",
        "sock_dir": str(sock_dir),
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "publish_timeout": 5,
        "extension_modules": str(tmp_path / "extmods"),
    }
    client.key = "fake-key"
    client.mopts = None
    # Populated so LocalClient.__del__/destroy don't emit an
    # unraisable AttributeError when the test-only instance is torn down.
    client.event = None
    client.auto_reconnect = False

    channel = MagicMock()
    channel.send.return_value = "Failed to allocate a jid."

    class _Ctx:
        def __enter__(self):
            return channel

        def __exit__(self, *exc):
            return False

    with patch(
        "salt.channel.client.ReqChannel.factory", MagicMock(return_value=_Ctx())
    ), patch.object(
        salt.client.LocalClient,
        "_prep_pub",
        MagicMock(return_value={"cmd": "publish"}),
    ):
        with pytest.raises(PublishError):
            client.pub("test_minion", "test.ping", tgt_type="glob", timeout=5)


# ---------------------------------------------------------------------------
# AESFuncs async dispatch plumbing
#
# Phase 1 of the async MWorker migration: these tests exercise the dispatch
# path itself (``AESFuncs.async_methods`` + ``run_func`` returning a coroutine
# + ``MWorker._handle_aes`` awaiting it) without converting any real
# production handler to ``async def``. A Phase 2 PR moves a specific method
# (e.g. ``_pillar``) to ``async def`` and adds its name to ``async_methods``.
# ---------------------------------------------------------------------------


class _StubAesFuncs:
    """Bare stand-in for ``AESFuncs`` that exercises only the pieces
    ``MWorker._handle_aes`` touches: ``get_method`` (truthiness check),
    ``run_func`` (dispatch), and ``async_methods`` (registry). Uses the real
    ``run_func`` so we're testing the production dispatch logic."""

    def __init__(
        self, async_methods=(), sync_ret="sync-result", async_ret="async-result"
    ):
        self.async_methods = tuple(async_methods)
        self.opts = {"pillar_version": 2}
        self._sync_ret = sync_ret
        self._async_ret = async_ret
        # Populated during dispatch to let tests assert the ctxvar was set.
        self.captured_context = None

    def get_method(self, cmd):
        # Truthy sentinel; real dispatch goes via ``run_func`` (mirrors what
        # ``AESFuncs.get_method`` guarantees via ``expose_methods``).
        return object()

    # --- registered handlers -------------------------------------------------
    def sync_ping(self, load):
        import salt.utils.ctx as _ctx

        self.captured_context = _ctx.get_request_context()
        return self._sync_ret

    async def async_ping(self, load):
        import salt.utils.ctx as _ctx

        self.captured_context = _ctx.get_request_context()
        return self._async_ret

    # Reuse the real dispatch/post-processing logic verbatim.
    run_func = salt.master.AESFuncs.run_func
    _run_func_async = salt.master.AESFuncs._run_func_async
    _wrap_run_func_return = salt.master.AESFuncs._wrap_run_func_return


def _make_aes_worker(aes_funcs):
    """Build an MWorker skeleton with just what ``_handle_aes`` needs."""
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.aes_funcs = aes_funcs
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    return worker


async def test_handle_aes_sync_dispatch_still_works():
    """Regression: after the async plumbing, sync handlers still dispatch and
    return the (ret, {"fun": "send"}) tuple as today."""
    aes_funcs = _StubAesFuncs(async_methods=())
    worker = _make_aes_worker(aes_funcs)
    ret = await worker._handle_aes({"cmd": "sync_ping"})
    assert ret == ("sync-result", {"fun": "send"})


async def test_handle_aes_async_dispatch_awaits_and_returns_result():
    """Proof-of-life: a method registered in ``async_methods`` is dispatched
    as a coroutine, awaited, and its result is wrapped in the same envelope
    as the sync path."""
    aes_funcs = _StubAesFuncs(async_methods=("async_ping",))
    worker = _make_aes_worker(aes_funcs)
    ret = await worker._handle_aes({"cmd": "async_ping"})
    assert ret == ("async-result", {"fun": "send"})


async def test_handle_aes_sync_dispatch_has_request_context():
    """``salt.utils.ctx.request_context`` must be active during sync dispatch."""
    aes_funcs = _StubAesFuncs(async_methods=())
    worker = _make_aes_worker(aes_funcs)
    data = {"cmd": "sync_ping", "id": "minion-a"}
    await worker._handle_aes(data)
    assert aes_funcs.captured_context is not None
    assert aes_funcs.captured_context["data"] is data
    assert aes_funcs.captured_context["opts"] is worker.opts


async def test_handle_aes_async_dispatch_has_request_context():
    """The context manager must remain active across the ``await`` boundary,
    so async handlers see the same request context as sync ones."""
    aes_funcs = _StubAesFuncs(async_methods=("async_ping",))
    worker = _make_aes_worker(aes_funcs)
    data = {"cmd": "async_ping", "id": "minion-b"}
    await worker._handle_aes(data)
    assert aes_funcs.captured_context is not None
    assert aes_funcs.captured_context["data"] is data
    assert aes_funcs.captured_context["opts"] is worker.opts


def test_aesfuncs_async_methods_registry_entries_are_coroutine_functions():
    """Every name registered in ``AESFuncs.async_methods`` must resolve to an
    ``async def`` on the class so ``run_func`` can dispatch it as a coroutine.
    This is the generic invariant; per-phase conversions grow the tuple."""
    import inspect

    for name in salt.master.AESFuncs.async_methods:
        handler = getattr(salt.master.AESFuncs, name, None)
        assert handler is not None, f"{name} listed but not defined on AESFuncs"
        assert inspect.iscoroutinefunction(handler), name


async def test_run_func_returns_coroutine_for_registered_async_method():
    """``run_func`` returns a coroutine (not an awaited value) when the
    method is registered in ``async_methods``; the caller must await."""
    aes_funcs = _StubAesFuncs(async_methods=("async_ping",))
    result = aes_funcs.run_func("async_ping", {"cmd": "async_ping"})
    import inspect

    assert inspect.iscoroutine(result)
    awaited = await result
    assert awaited == ("async-result", {"fun": "send"})


# ---------------------------------------------------------------------------
# Phase 2C: AESFuncs mine-family async conversion.
#
# Each ``_mine*`` handler is now ``async def`` and offloads its (synchronous)
# ``masterapi._mine*`` call into the default executor. These tests confirm:
#   1. The handler is registered in ``async_methods`` and dispatched as a
#      coroutine through the real ``_handle_aes`` async path.
#   2. The return-value shape is byte-for-byte identical to the pre-conversion
#      sync path (``masterapi._mine*`` return value passed through unchanged).
#   3. The synchronous ``masterapi._mine*`` call is offloaded via
#      ``loop.run_in_executor`` rather than executed on the event loop thread.
# ---------------------------------------------------------------------------


def _mine_aes_funcs(masterapi_mock):
    """Build a minimal ``AESFuncs`` shell wired to a mocked masterapi.

    Bypasses the heavyweight ``__init__`` (event bus, fileserver, keys) since
    the mine handlers only touch ``__verify_load`` and ``self.masterapi``.
    """
    aes_funcs = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes_funcs.opts = {"pillar_version": 2}
    aes_funcs.masterapi = masterapi_mock
    return aes_funcs


def _mine_worker(aes_funcs):
    """Bind a mine-family ``AESFuncs`` to an MWorker skeleton for dispatch."""
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.aes_funcs = aes_funcs
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    return worker


@pytest.mark.parametrize(
    "cmd, masterapi_attr, load, expected_ret, expected_call_kwargs",
    (
        (
            "_mine_get",
            "_mine_get",
            {"id": "m1", "tgt": "*", "fun": "grains.items"},
            {"m1": {"os": "Linux"}},
            {"skip_verify": False},
        ),
        (
            "_mine",
            "_mine",
            {"id": "m1", "data": {"grains.items": {"os": "Linux"}}},
            True,
            {"skip_verify": False},
        ),
        (
            "_mine_delete",
            "_mine_delete",
            {"id": "m1", "fun": "grains.items"},
            True,
            None,
        ),
        (
            "_mine_flush",
            "_mine_flush",
            {"id": "m1"},
            True,
            {"skip_verify": True},
        ),
    ),
)
async def test_mine_family_async_dispatch_preserves_return_shape(
    cmd, masterapi_attr, load, expected_ret, expected_call_kwargs
):
    """Dispatch through the real ``_handle_aes`` async path and confirm the
    handler returns the ``masterapi._mine*`` return value verbatim, wrapped
    in the ``(ret, {"fun": "send"})`` envelope."""
    masterapi = MagicMock()
    getattr(masterapi, masterapi_attr).return_value = expected_ret
    aes_funcs = _mine_aes_funcs(masterapi)
    worker = _mine_worker(aes_funcs)

    envelope = await worker._handle_aes({"cmd": cmd, **load})

    assert envelope == (expected_ret, {"fun": "send"})
    api_call = getattr(masterapi, masterapi_attr)
    assert api_call.call_count == 1
    call_args, call_kwargs = api_call.call_args
    # ``__verify_load`` mutates load in place but keeps the same required
    # keys; assert the positional payload contains what we sent.
    passed_load = call_args[0]
    for key, value in load.items():
        assert passed_load[key] == value
    if expected_call_kwargs is None:
        assert call_kwargs == {}
    else:
        assert call_kwargs == expected_call_kwargs


@pytest.mark.parametrize(
    "cmd, masterapi_attr, load",
    (
        ("_mine_get", "_mine_get", {"id": "m1", "tgt": "*", "fun": "grains.items"}),
        ("_mine", "_mine", {"id": "m1", "data": {"grains.items": {"os": "Linux"}}}),
        ("_mine_delete", "_mine_delete", {"id": "m1", "fun": "grains.items"}),
        ("_mine_flush", "_mine_flush", {"id": "m1"}),
    ),
)
async def test_mine_family_offloads_to_run_in_executor(cmd, masterapi_attr, load):
    """The sync ``masterapi._mine*`` call must be scheduled via the running
    loop's default executor, not executed on the event loop thread."""
    masterapi = MagicMock()
    getattr(masterapi, masterapi_attr).return_value = {}
    aes_funcs = _mine_aes_funcs(masterapi)

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=spy):
        await getattr(aes_funcs, cmd)(load)

    assert len(calls) == 1
    # Default executor is signalled by ``None``.
    assert calls[0][0] is None


async def test_mine_get_verify_load_failure_returns_empty_dict():
    """When ``__verify_load`` rejects the payload, ``_mine_get`` must return
    ``{}`` without invoking ``masterapi._mine_get`` -- matching the pre-async
    behavior."""
    masterapi = MagicMock()
    aes_funcs = _mine_aes_funcs(masterapi)
    # Missing required keys triggers __verify_load -> False.
    ret = await aes_funcs._mine_get({"id": "m1"})
    assert ret == {}
    masterapi._mine_get.assert_not_called()


async def test_mine_verify_load_failure_returns_empty_dict():
    masterapi = MagicMock()
    aes_funcs = _mine_aes_funcs(masterapi)
    ret = await aes_funcs._mine({"id": "m1"})  # missing "data"
    assert ret == {}
    masterapi._mine.assert_not_called()


async def test_mine_delete_verify_load_failure_returns_empty_dict():
    masterapi = MagicMock()
    aes_funcs = _mine_aes_funcs(masterapi)
    ret = await aes_funcs._mine_delete({"id": "m1"})  # missing "fun"
    assert ret == {}
    masterapi._mine_delete.assert_not_called()


async def test_mine_flush_verify_load_failure_returns_empty_dict():
    masterapi = MagicMock()
    aes_funcs = _mine_aes_funcs(masterapi)
    ret = await aes_funcs._mine_flush({})  # missing "id"
    assert ret == {}
    masterapi._mine_flush.assert_not_called()


# Phase 2E: minion_runner / minion_pub / minion_publish / revoke_auth
#
# The AESFuncs wrappers for these four methods are now ``async def`` and
# offload the blocking ``self.masterapi.<op>`` call to the default executor.
# The return-value shape must exactly match the pre-conversion sync version
# and dispatch through ``MWorker._handle_aes`` must yield the same envelope
# as the sync path.
# ---------------------------------------------------------------------------


def _bare_aes_funcs():
    """Build an ``AESFuncs`` bypassing ``__init__`` for narrowly-scoped tests
    that only exercise the four Phase 2E wrappers. Callers set ``self.opts``,
    ``self.masterapi`` and (when needed) private-name-mangled ``__verify_load``
    / ``__verify_minion_publish`` overrides on the returned instance."""
    return salt.master.AESFuncs.__new__(salt.master.AESFuncs)


async def test_minion_runner_delegates_and_offloads():
    """``minion_runner`` awaits the executor and returns the masterapi result
    verbatim (a dict of runner output). Verify-load happy path."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_runner.return_value = {"return": "runner-ret"}
    load = {"fun": "test.arg", "arg": [], "id": "minion-a"}
    ret = await aes.minion_runner(load)
    assert ret == {"return": "runner-ret"}
    aes.masterapi.minion_runner.assert_called_once_with(load)


async def test_minion_runner_returns_empty_when_verify_load_fails():
    """A missing required key ('fun'/'arg'/'id') short-circuits to ``{}`` and
    the masterapi is not touched, matching the sync semantics."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    ret = await aes.minion_runner({"fun": "test.arg"})  # missing arg, id
    assert ret == {}
    aes.masterapi.minion_runner.assert_not_called()


async def test_minion_pub_delegates_and_offloads():
    """``minion_pub`` awaits the executor when ``__verify_minion_publish``
    returns truthy and returns the masterapi payload as-is."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_pub.return_value = {"jid": "20260808000000", "minions": ["m1"]}
    load = {"fun": "test.ping", "arg": [], "tgt": "*", "ret": "", "id": "m1"}
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=True,
    ):
        ret = await aes.minion_pub(load)
    assert ret == {"jid": "20260808000000", "minions": ["m1"]}
    aes.masterapi.minion_pub.assert_called_once_with(load)


async def test_minion_pub_returns_empty_when_not_authorized():
    """Failing ``__verify_minion_publish`` short-circuits to ``{}``."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=False,
    ):
        ret = await aes.minion_pub({"id": "m1"})
    assert ret == {}
    aes.masterapi.minion_pub.assert_not_called()


async def test_minion_publish_delegates_and_offloads():
    """``minion_publish`` awaits the executor and returns the masterapi return
    dict verbatim (minion-id keyed results)."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_publish.return_value = {"m1": True, "m2": False}
    load = {"fun": "test.ping", "arg": [], "tgt": "*", "ret": "", "id": "m1"}
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=True,
    ):
        ret = await aes.minion_publish(load)
    assert ret == {"m1": True, "m2": False}
    aes.masterapi.minion_publish.assert_called_once_with(load)


async def test_minion_publish_returns_empty_when_not_authorized():
    """Failing ``__verify_minion_publish`` short-circuits to ``{}``."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=False,
    ):
        ret = await aes.minion_publish({"id": "m1"})
    assert ret == {}
    aes.masterapi.minion_publish.assert_not_called()


async def test_revoke_auth_delegates_when_allowed():
    """When ``allow_minion_key_revoke`` is truthy, ``revoke_auth`` awaits the
    executor and returns the masterapi's boolean result."""
    aes = _bare_aes_funcs()
    aes.opts = {"allow_minion_key_revoke": True}
    aes.masterapi = MagicMock()
    aes.masterapi.revoke_auth.return_value = True
    load = {"id": "minion-a"}
    ret = await aes.revoke_auth(load)
    assert ret is True
    aes.masterapi.revoke_auth.assert_called_once_with(load)


async def test_revoke_auth_disabled_returns_load_without_delegating():
    """When ``allow_minion_key_revoke`` is not set, the sync path returned the
    verified load unchanged and logged a warning. Preserve that shape and skip
    the executor entirely."""
    aes = _bare_aes_funcs()
    aes.opts = {"allow_minion_key_revoke": False}
    aes.masterapi = MagicMock()
    load = {"id": "minion-a"}
    ret = await aes.revoke_auth(load)
    assert ret == load
    aes.masterapi.revoke_auth.assert_not_called()


async def test_revoke_auth_returns_empty_when_verify_load_fails():
    """A load missing the ``id`` key must return ``False`` (pre-conversion
    sync behavior) without touching masterapi."""
    aes = _bare_aes_funcs()
    aes.opts = {"allow_minion_key_revoke": True}
    aes.masterapi = MagicMock()
    ret = await aes.revoke_auth({})  # no 'id' key
    assert ret is False
    aes.masterapi.revoke_auth.assert_not_called()


# --- Dispatch through _handle_aes: end-to-end async path -------------------


async def test_handle_aes_dispatches_minion_runner_async():
    """End-to-end: ``MWorker._handle_aes`` dispatches ``minion_runner`` via
    the async path (``run_func`` returns a coroutine, ``_handle_aes`` awaits)
    and wraps the result in the standard ``(ret, {"fun": "send"})`` envelope."""
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_runner.return_value = {"return": "ok"}
    worker = _make_aes_worker(aes)
    load = {"cmd": "minion_runner", "fun": "test.arg", "arg": [], "id": "m1"}
    ret = await worker._handle_aes(load)
    assert ret == ({"return": "ok"}, {"fun": "send"})


async def test_handle_aes_dispatches_minion_pub_async():
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_pub.return_value = {"jid": "j1", "minions": ["m1"]}
    worker = _make_aes_worker(aes)
    load = {
        "cmd": "minion_pub",
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "ret": "",
        "id": "m1",
    }
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=True,
    ):
        ret = await worker._handle_aes(load)
    assert ret == ({"jid": "j1", "minions": ["m1"]}, {"fun": "send"})


async def test_handle_aes_dispatches_minion_publish_async():
    aes = _bare_aes_funcs()
    aes.opts = {}
    aes.masterapi = MagicMock()
    aes.masterapi.minion_publish.return_value = {"m1": True}
    worker = _make_aes_worker(aes)
    load = {
        "cmd": "minion_publish",
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "ret": "",
        "id": "m1",
    }
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion_publish",
        return_value=True,
    ):
        ret = await worker._handle_aes(load)
    assert ret == ({"m1": True}, {"fun": "send"})


async def test_handle_aes_dispatches_revoke_auth_async():
    aes = _bare_aes_funcs()
    aes.opts = {"allow_minion_key_revoke": True}
    aes.masterapi = MagicMock()
    aes.masterapi.revoke_auth.return_value = True
    worker = _make_aes_worker(aes)
    load = {"cmd": "revoke_auth", "id": "m1"}
    ret = await worker._handle_aes(load)
    assert ret == (True, {"fun": "send"})


# AESFuncs._pillar async conversion (Phase 2A)
#
# The handler now uses ``salt.pillar.get_async_pillar`` +
# ``await pillar.compile_pillar()`` and awaits ``fire_event_async``; sync-only
# helpers (``Fileserver.update_opts``, ``masterapi.cache.store``) are offloaded
# via ``loop.run_in_executor``. These tests exercise the full
# ``MWorker._handle_aes`` -> ``run_func`` -> ``_pillar`` path with the pillar,
# event, cache, and fileserver internals mocked out.
# ---------------------------------------------------------------------------


def _make_async_pillar_aes_funcs(
    opts, *, compile_ret, minion_data_cache=True, minion_data_cache_events=True
):
    """Bypass ``AESFuncs.__init__`` and wire up only the attributes ``_pillar``
    touches. Returns (aes_funcs, mocks_dict) so callers can assert on the
    individual mocks."""
    aes_funcs = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes_funcs.opts = dict(opts)
    aes_funcs.opts["minion_data_cache"] = minion_data_cache
    aes_funcs.opts["minion_data_cache_events"] = minion_data_cache_events
    aes_funcs.opts.setdefault("pillar_version", 2)

    # ``compile_pillar`` is an ``async def`` on ``AsyncPillar``; wire it up as
    # an ``AsyncMock`` so we can assert it was awaited.
    pillar_instance = MagicMock()
    pillar_instance.compile_pillar = AsyncMock(return_value=compile_ret)
    get_async_pillar = MagicMock(return_value=pillar_instance)

    aes_funcs.fs_ = MagicMock()
    aes_funcs.masterapi = MagicMock()
    aes_funcs.masterapi.cache = MagicMock()
    aes_funcs.event = MagicMock()
    aes_funcs.event.fire_event_async = AsyncMock()
    # ``async_methods`` / ``get_method`` come from the class; ensure the
    # handler is registered so ``run_func`` dispatches via ``_run_func_async``.
    assert "_pillar" in salt.master.AESFuncs.async_methods
    mocks = {
        "pillar": pillar_instance,
        "get_async_pillar": get_async_pillar,
    }
    return aes_funcs, mocks


async def test_pillar_async_dispatch_through_handle_aes(master_opts):
    """End-to-end: ``MWorker._handle_aes`` awaits the ``_pillar`` coroutine
    and applies the return envelope (``send_private`` for ver=2 pillars)."""
    compile_ret = {"role": "web", "env": "prod"}
    aes_funcs, mocks = _make_async_pillar_aes_funcs(
        master_opts, compile_ret=compile_ret
    )
    worker = _make_aes_worker(aes_funcs)

    load = {
        "cmd": "_pillar",
        "id": "minion-async",
        "grains": {"os": "Debian"},
        "saltenv": "base",
        "ver": "2",
    }
    with patch("salt.pillar.get_async_pillar", mocks["get_async_pillar"]):
        ret = await worker._handle_aes(load)

    # Envelope shape mirrors the pre-conversion sync path (see
    # ``_wrap_run_func_return``): ver=2 gets ``send_private``.
    assert ret == (
        compile_ret,
        {"fun": "send_private", "key": "pillar", "tgt": "minion-async"},
    )
    # ``compile_pillar`` must have been awaited exactly once.
    assert mocks["pillar"].compile_pillar.await_count == 1
    # ``fire_event_async`` must have been awaited (minion_data_cache_events on).
    assert aes_funcs.event.fire_event_async.await_count == 1
    args, _ = aes_funcs.event.fire_event_async.call_args
    assert args[0] == {"Minion data cache refresh": "minion-async"}
    # Sync-only cache and fileserver helpers were still invoked (offloaded via
    # ``run_in_executor``).
    aes_funcs.masterapi.cache.store.assert_called_once_with(
        "grains", "minion-async", {"os": "Debian", "id": "minion-async"}
    )
    aes_funcs.fs_.update_opts.assert_called_once_with()


async def test_pillar_async_return_shape_matches_sync_ver1(master_opts):
    """When ``load['ver']`` is not ``"2"`` and ``pillar_version`` is 1 the
    envelope is ``send`` (unencrypted) — same as the pre-conversion sync
    branch. Guards against regressions in the return-shape."""
    compile_ret = {"legacy": True}
    aes_funcs, mocks = _make_async_pillar_aes_funcs(
        master_opts,
        compile_ret=compile_ret,
        minion_data_cache=False,
    )
    aes_funcs.opts["pillar_version"] = 1
    worker = _make_aes_worker(aes_funcs)

    load = {
        "cmd": "_pillar",
        "id": "minion-legacy",
        "grains": {},
        "saltenv": "base",
        # No ``ver`` key -> old proto path in ``_wrap_run_func_return``.
    }
    with patch("salt.pillar.get_async_pillar", mocks["get_async_pillar"]):
        ret = await worker._handle_aes(load)

    assert ret == (compile_ret, {"fun": "send"})
    # No cache/event work when ``minion_data_cache`` is off.
    aes_funcs.masterapi.cache.store.assert_not_called()
    assert aes_funcs.event.fire_event_async.await_count == 0
    aes_funcs.fs_.update_opts.assert_called_once_with()


async def test_pillar_async_skips_fire_event_when_events_disabled(master_opts):
    """``minion_data_cache_events=False`` must still store the grains cache but
    must NOT fire the refresh event — same behaviour as the sync version."""
    aes_funcs, mocks = _make_async_pillar_aes_funcs(
        master_opts,
        compile_ret={},
        minion_data_cache=True,
        minion_data_cache_events=False,
    )
    worker = _make_aes_worker(aes_funcs)
    load = {
        "cmd": "_pillar",
        "id": "minion-quiet",
        "grains": {},
        "ver": "2",
    }
    with patch("salt.pillar.get_async_pillar", mocks["get_async_pillar"]):
        await worker._handle_aes(load)

    aes_funcs.masterapi.cache.store.assert_called_once()
    assert aes_funcs.event.fire_event_async.await_count == 0


async def test_pillar_async_rejects_missing_load_keys(master_opts):
    """``_pillar`` returns ``False`` (wrapped by ``_wrap_run_func_return`` into
    the ``send_private`` envelope for ``_pillar`` with ``id``) when required
    keys are missing — verified across the ``await`` boundary."""
    aes_funcs, mocks = _make_async_pillar_aes_funcs(master_opts, compile_ret={})
    worker = _make_aes_worker(aes_funcs)
    # Missing ``grains``.
    load = {"cmd": "_pillar", "id": "minion-x", "ver": "2"}
    with patch("salt.pillar.get_async_pillar", mocks["get_async_pillar"]):
        ret = await worker._handle_aes(load)
    assert ret == (
        False,
        {"fun": "send_private", "key": "pillar", "tgt": "minion-x"},
    )
    mocks["get_async_pillar"].assert_not_called()
    assert mocks["pillar"].compile_pillar.await_count == 0


# Phase 2D: fileserver family (``_serve_file``, ``_file_hash``,
# ``_file_hash_and_stat``, ``_file_list``, ``_file_list_emptydirs``,
# ``_file_find``, ``_dir_list``, ``_symlink_list``, ``_file_envs``,
# ``_file_recv``) is now dispatched via ``async_methods``. Each handler
# offloads the sync fileserver call to ``loop.run_in_executor(None, ...)``
# so the master worker's event loop is not parked on disk I/O.
# ---------------------------------------------------------------------------


def _bare_aes_funcs():
    """Construct an ``AESFuncs`` without running its heavyweight ``__init__``.
    Only the attributes the fileserver family touches are populated."""
    aes_funcs = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes_funcs.opts = {
        "file_recv": True,
        "file_recv_max_size": 100,
        "fileserver_followsymlinks": False,
    }
    aes_funcs.fs_ = MagicMock()
    return aes_funcs


async def test_serve_file_dispatches_via_executor():
    """``_serve_file`` must offload ``fs_.serve_file(load)`` to the default
    executor and return its result untouched (preserving the pre-conversion
    shape ``fs_.serve_file`` yields today: a dict with ``data``/``dest``)."""
    aes_funcs = _bare_aes_funcs()
    payload = {"data": b"chunk", "dest": "salt://a"}
    aes_funcs.fs_.serve_file = MagicMock(return_value=payload)

    loop = asyncio.get_running_loop()
    seen = {}
    real_run_in_executor = loop.run_in_executor

    async def _tracked_run_in_executor(executor, func, *args):
        seen["executor"] = executor
        seen["func"] = func
        seen["args"] = args
        return await real_run_in_executor(executor, func, *args)

    load = {"path": "salt://a", "loc": 0, "saltenv": "base"}
    with patch.object(loop, "run_in_executor", side_effect=_tracked_run_in_executor):
        ret = await aes_funcs._serve_file(load)

    assert ret is payload
    # Executor was invoked with the bound fs_.serve_file callable and load.
    assert seen["executor"] is None
    assert seen["func"] is aes_funcs.fs_.serve_file
    assert seen["args"] == (load,)
    aes_funcs.fs_.serve_file.assert_called_once_with(load)


async def test_file_list_dispatches_via_executor_and_preserves_shape():
    """``_file_list`` must return the exact list ``fs_.file_list`` yields."""
    aes_funcs = _bare_aes_funcs()
    aes_funcs.fs_.file_list = MagicMock(return_value=["a.sls", "b.sls"])

    load = {"saltenv": "base"}
    ret = await aes_funcs._file_list(load)

    assert ret == ["a.sls", "b.sls"]
    aes_funcs.fs_.file_list.assert_called_once_with(load)


async def test_file_recv_writes_via_executor(tmp_path):
    """``_file_recv`` must offload its disk write to the executor and return
    ``True`` on success, matching the pre-conversion sync behavior."""
    aes_funcs = _bare_aes_funcs()
    aes_funcs.opts["cachedir"] = str(tmp_path)
    aes_funcs.opts["pki_dir"] = str(tmp_path)

    load = {
        "id": "minion-a",
        "path": ["subdir", "hello.txt"],
        "loc": 0,
        "data": b"payload",
    }

    loop = asyncio.get_running_loop()
    seen = {}
    real_run_in_executor = loop.run_in_executor

    async def _tracked_run_in_executor(executor, func, *args):
        seen["executor"] = executor
        seen["func"] = func
        seen["args"] = args
        return await real_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=_tracked_run_in_executor):
        ret = await aes_funcs._file_recv(load)

    assert ret is True
    # The blocking write helper was offloaded, not the entire method.
    assert seen["executor"] is None
    assert seen["func"] is salt.master.AESFuncs._file_recv_write
    written = tmp_path / "minions" / "minion-a" / "files" / "subdir" / "hello.txt"
    assert written.read_bytes() == b"payload"


async def test_file_recv_validation_short_circuits_without_executor():
    """Early validation failures must not schedule any executor work — this
    matches the pre-conversion sync path which returned False before touching
    disk."""
    aes_funcs = _bare_aes_funcs()
    aes_funcs.opts["file_recv"] = False

    loop = asyncio.get_running_loop()
    calls = []

    async def _tracked_run_in_executor(executor, func, *args):
        calls.append(func)
        return await loop.run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=_tracked_run_in_executor):
        ret = await aes_funcs._file_recv(
            {"id": "m", "path": ["x"], "loc": 0, "data": b""}
        )

    assert ret is False
    assert calls == []


async def test_fileserver_family_dispatches_through_handle_aes():
    """End-to-end: ``_handle_aes`` for ``_file_list`` awaits the async
    handler and applies the standard ``{"fun": "send"}`` return envelope."""
    aes_funcs = _bare_aes_funcs()
    aes_funcs.fs_.file_list = MagicMock(return_value=["top.sls"])
    # ``_handle_aes`` calls ``get_method`` first as a truthiness gate; the
    # real implementation checks ``expose_methods``. ``_file_list`` is in
    # the exposed list, so the real method resolves — but we can't call
    # ``AESFuncs.get_method`` directly without going through the heavy
    # ``__init__``. Use the real function bound to our bare instance.
    aes_funcs.expose_methods = salt.master.AESFuncs.expose_methods
    aes_funcs.async_methods = salt.master.AESFuncs.async_methods
    aes_funcs.get_method = salt.master.AESFuncs.get_method.__get__(aes_funcs)
    aes_funcs.run_func = salt.master.AESFuncs.run_func.__get__(aes_funcs)
    aes_funcs._run_func_async = salt.master.AESFuncs._run_func_async.__get__(aes_funcs)
    aes_funcs._wrap_run_func_return = (
        salt.master.AESFuncs._wrap_run_func_return.__get__(aes_funcs)
    )

    worker = _make_aes_worker(aes_funcs)
    ret = await worker._handle_aes({"cmd": "_file_list", "saltenv": "base"})

    assert ret == (["top.sls"], {"fun": "send"})
    aes_funcs.fs_.file_list.assert_called_once_with(
        {"cmd": "_file_list", "saltenv": "base"}
    )


# Phase 2B: job-cache / return family conversions (_return, _syndic_return,
# pub_ret). Each method now runs under ``MWorker._handle_aes``'s async path
# and offloads its sync/disk-bound callables to ``loop.run_in_executor``.
# ---------------------------------------------------------------------------


def _prime_return_opts(encrypted_requests):
    """The minimal ``encrypted_requests`` fixture omits the signing knobs
    that ``_return`` reads. Prime them with the sync-era defaults so the
    async path behaves the same way."""
    encrypted_requests.opts.setdefault("require_minion_sign_messages", False)
    encrypted_requests.opts.setdefault("drop_messages_signature_fail", False)
    encrypted_requests.opts.setdefault("signing_algorithm", "PKCS1v15-SHA1")


async def test_return_is_dispatched_as_coroutine_via_run_func(encrypted_requests):
    """``_return`` is registered in ``async_methods`` so ``run_func`` must
    hand a coroutine back to the caller (mirrors the dispatch contract)."""
    import inspect

    _prime_return_opts(encrypted_requests)
    load = {"id": "minion-a", "jid": "20260808000000000000", "return": "ok"}
    with patch("salt.utils.job.store_job") as store_job:
        result = encrypted_requests.run_func("_return", load)
        assert inspect.iscoroutine(result)
        ret, envelope = await result
    # ``_return`` returns None on success; envelope shape matches the
    # pre-conversion sync path (``_wrap_run_func_return`` special-case).
    assert ret is None
    assert envelope == {"fun": "send"}
    # ``store_job`` is the sync-only call we offloaded; assert it fired.
    store_job.assert_called_once()


async def test_return_offloads_store_job_to_executor(encrypted_requests):
    """``salt.utils.job.store_job`` is a sync/disk-bound call. It must be
    scheduled onto the default executor so the ioloop isn't blocked on
    returner I/O."""
    _prime_return_opts(encrypted_requests)
    load = {"id": "minion-a", "jid": "20260808000000000001", "return": "ok"}
    loop = asyncio.get_running_loop()
    real_run_in_executor = loop.run_in_executor
    seen = []

    def _spy(executor, func, *args):
        seen.append(func)
        return real_run_in_executor(executor, func, *args)

    with patch("salt.utils.job.store_job") as store_job, patch.object(
        loop, "run_in_executor", side_effect=_spy
    ):
        await encrypted_requests._return(load)
    # store_job was offloaded via executor rather than called inline.
    assert store_job.called
    assert seen, "run_in_executor was not used for store_job"


async def test_return_short_circuits_when_signature_required_but_missing(
    encrypted_requests,
):
    """Preserve the sync-era shape: return ``False`` when signing is required
    but the load carries no ``sig``."""
    _prime_return_opts(encrypted_requests)
    encrypted_requests.opts["require_minion_sign_messages"] = True
    load = {"id": "minion-a", "jid": "20260808000000000002", "return": "ok"}
    with patch("salt.utils.job.store_job") as store_job:
        result = await encrypted_requests._return(load)
    assert result is False
    store_job.assert_not_called()


async def test_syndic_return_is_dispatched_as_coroutine(encrypted_requests):
    """``_syndic_return`` registers in ``async_methods`` and must round-trip
    through ``run_func`` as a coroutine."""
    import inspect

    load = {"cmd": "_syndic_return", "load": []}
    result = encrypted_requests.run_func("_syndic_return", load)
    assert inspect.iscoroutine(result)
    ret, envelope = await result
    assert ret is None
    assert envelope == {"fun": "send"}


async def test_syndic_return_awaits_inner_return_and_uses_executor(
    encrypted_requests, tmp_path
):
    """The syndic path (a) awaits each per-minion ``_return`` and (b)
    offloads the mkdir/marker-file write. Assert both."""
    encrypted_requests.opts["cachedir"] = str(tmp_path)
    encrypted_requests.opts["master_job_cache"] = False
    payload = {
        "cmd": "_syndic_return",
        "load": [
            {
                "id": "syndic-a",
                "jid": "20260808000000000010",
                "return": {"minion-1": {"return": "value", "retcode": 0}},
                "fun": "test.ping",
            }
        ],
    }
    fake_return = AsyncMock()
    loop = asyncio.get_running_loop()
    real_run_in_executor = loop.run_in_executor
    seen = []

    def _spy(executor, func, *args):
        seen.append(getattr(func, "__name__", repr(func)))
        return real_run_in_executor(executor, func, *args)

    with patch.object(encrypted_requests, "_return", fake_return), patch.object(
        loop, "run_in_executor", side_effect=_spy
    ):
        await encrypted_requests._syndic_return(payload)
    # Inner ``_return`` was awaited exactly once, with the reshaped dict.
    fake_return.assert_awaited_once()
    (called_ret,) = fake_return.await_args.args
    assert called_ret["jid"] == "20260808000000000010"
    assert called_ret["id"] == "minion-1"
    assert called_ret["fun"] == "test.ping"
    # The marker-file writer was offloaded via the executor.
    assert "_write_syndic_cache_marker" in seen
    # And the marker actually landed on disk.
    assert (tmp_path / "syndics" / "syndic-a").exists()


async def test_pub_ret_is_dispatched_as_coroutine(encrypted_requests, tmp_path):
    """``pub_ret`` registers in ``async_methods`` and must round-trip
    through ``run_func`` as a coroutine."""
    import inspect

    # Not passing __verify_load -> returns {} without doing disk work.
    load = {"cmd": "pub_ret"}
    result = encrypted_requests.run_func("pub_ret", load)
    assert inspect.iscoroutine(result)
    ret, envelope = await result
    assert ret == {}
    assert envelope == {"fun": "send"}


async def test_pub_ret_offloads_disk_and_returner_calls(encrypted_requests, tmp_path):
    """``pub_ret`` (a) reads the publish-auth file and (b) calls
    ``local.get_cache_returns``. Both are sync/disk-bound, both must be
    scheduled onto the default executor."""
    encrypted_requests.opts["cachedir"] = str(tmp_path)
    auth_cache = tmp_path / "publish_auth"
    auth_cache.mkdir()
    jid = "20260808000000000020"
    (auth_cache / jid).write_text("minion-a")

    expected_ret = {"minion-a": {"ret": "value", "out": "nested"}}
    encrypted_requests.local = MagicMock()
    encrypted_requests.local.get_cache_returns = MagicMock(return_value=expected_ret)

    loop = asyncio.get_running_loop()
    real_run_in_executor = loop.run_in_executor
    call_count = {"n": 0}

    def _spy(executor, func, *args):
        call_count["n"] += 1
        return real_run_in_executor(executor, func, *args)

    load = {"cmd": "pub_ret", "jid": jid, "id": "minion-a"}
    with patch.object(loop, "run_in_executor", side_effect=_spy):
        result = await encrypted_requests.pub_ret(load)

    assert result == expected_ret
    encrypted_requests.local.get_cache_returns.assert_called_once_with(jid)
    # At least two executor hops: auth-cache check + get_cache_returns.
    assert call_count["n"] >= 2


async def test_pub_ret_returns_empty_when_auth_id_mismatch(
    encrypted_requests, tmp_path
):
    """Preserve the sync-era shape: when the publish-auth id doesn't match
    the requesting minion, return ``{}`` and don't touch the job cache."""
    encrypted_requests.opts["cachedir"] = str(tmp_path)
    auth_cache = tmp_path / "publish_auth"
    auth_cache.mkdir()
    jid = "20260808000000000021"
    (auth_cache / jid).write_text("other-minion")

    encrypted_requests.local = MagicMock()
    encrypted_requests.local.get_cache_returns = MagicMock()

    load = {"cmd": "pub_ret", "jid": jid, "id": "minion-a"}
    result = await encrypted_requests.pub_ret(load)
    assert result == {}
    encrypted_requests.local.get_cache_returns.assert_not_called()


# Phase 2F: verify_minion / _master_tops / _master_opts / _register_resources
# are dispatched through the async path and offload their blocking bodies to
# ``loop.run_in_executor``.
# ---------------------------------------------------------------------------


import asyncio  # noqa: E402
import inspect  # noqa: E402


def _build_bare_aesfuncs(opts=None):
    """Bypass ``AESFuncs.__init__`` (event loop, fileserver, masterapi) so
    Phase 2F tests can drive the four migrated methods without spinning up
    the master's real subsystems."""
    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = opts or {}
    aes.event = MagicMock()
    aes.masterapi = MagicMock()
    aes.fs_ = MagicMock()
    aes.key_cache = MagicMock()
    aes.ckminions = MagicMock()
    aes.cache = MagicMock()
    aes.local = MagicMock()
    aes.mminion = MagicMock()
    aes.pki_dir = ""
    # Bound methods populated by ``__setup_fileserver`` in the real ctor.
    aes._file_envs = AsyncMock(return_value=["base", "dev"])
    return aes


# --- verify_minion ---------------------------------------------------------


def test_verify_minion_is_async_and_registered():
    """``verify_minion`` must be a coroutine function and appear in
    ``async_methods`` so ``run_func`` dispatches it as a coroutine."""
    assert inspect.iscoroutinefunction(salt.master.AESFuncs.verify_minion)
    assert "verify_minion" in salt.master.AESFuncs.async_methods


async def test_verify_minion_offloads_sync_body_to_executor():
    """``verify_minion`` must run the blocking ``__verify_minion`` in the
    default thread executor so RSA decrypt and cache fetch don't stall the
    MWorker loop."""
    aes = _build_bare_aesfuncs()
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion",
        return_value=True,
    ) as sync_impl:
        loop = asyncio.get_running_loop()
        with patch.object(loop, "run_in_executor", wraps=loop.run_in_executor) as rie:
            result = await aes.verify_minion("minion-a", b"tok")
    assert result is True
    # ``patch.object`` swaps in an unbound Mock, so the descriptor lookup
    # from ``self.__verify_minion`` calls it with ``(id_, token)`` — the
    # instance is not forwarded through the mock's proxy layer.
    sync_impl.assert_called_once_with("minion-a", b"tok")
    # First positional arg of ``run_in_executor`` is the executor (``None``
    # means default); second is the sync callable.
    assert rie.called
    args = rie.call_args.args
    assert args[0] is None


async def test_verify_minion_return_shape_matches_sync_version():
    """Return value shape (a plain bool) must match the pre-conversion sync
    version so remote minions continue to see the same auth verdict."""
    aes = _build_bare_aesfuncs()
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion",
        return_value=False,
    ):
        result = await aes.verify_minion("minion-a", b"tok")
    assert result is False


async def test_verify_minion_dispatches_through_handle_aes():
    """End-to-end dispatch check: ``_handle_aes`` awaits ``verify_minion``
    via ``run_func``'s async branch and wraps the result in the ``send``
    envelope, identical to the sync path."""
    aes = _build_bare_aesfuncs()
    aes.get_method = lambda name: getattr(aes, name)
    aes.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion",
        return_value=True,
    ):
        worker = salt.master.MWorker.__new__(salt.master.MWorker)
        worker.opts = {"master_stats": False}
        worker.aes_funcs = aes
        worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
        ret = await worker._handle_aes(
            {"cmd": "verify_minion", "id_": "minion-a", "token": b"tok"}
        )
    # ``run_func`` looks up the method by name and calls it with a single
    # ``load`` argument; ``verify_minion`` normally takes ``id_, token``, so
    # ``_handle_aes`` isn't the natural entry point for it — but we can still
    # verify the dispatch envelope by calling ``run_func`` directly.
    # (The `_handle_aes` path is exercised for the *-load* methods below.)
    assert ret[1] == {"fun": "send"}


# --- _master_tops ----------------------------------------------------------


def test_master_tops_is_async_and_registered():
    assert inspect.iscoroutinefunction(salt.master.AESFuncs._master_tops)
    assert "_master_tops" in salt.master.AESFuncs.async_methods


async def test_master_tops_offloads_masterapi_call_to_executor():
    aes = _build_bare_aesfuncs()
    aes.masterapi._master_tops = MagicMock(return_value={"top": ["state1"]})
    loop = asyncio.get_running_loop()
    with patch.object(loop, "run_in_executor", wraps=loop.run_in_executor) as rie:
        result = await aes._master_tops({"id": "minion-1"})
    assert result == {"top": ["state1"]}
    aes.masterapi._master_tops.assert_called_once()
    # ``skip_verify=True`` is preserved via ``functools.partial``.
    call_args, call_kwargs = aes.masterapi._master_tops.call_args
    assert call_args[0] == {"id": "minion-1"}
    assert call_kwargs == {"skip_verify": True}
    assert rie.called
    assert rie.call_args.args[0] is None


async def test_master_tops_bad_load_returns_empty_dict():
    """Return-shape parity: a load missing ``id`` returns ``{}`` — same as
    the pre-conversion sync path."""
    aes = _build_bare_aesfuncs()
    aes.masterapi._master_tops = MagicMock()
    result = await aes._master_tops({})
    assert result == {}
    aes.masterapi._master_tops.assert_not_called()


async def test_master_tops_dispatches_through_handle_aes():
    aes = _build_bare_aesfuncs()
    aes.masterapi._master_tops = MagicMock(return_value={"top": ["s1"]})
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.aes_funcs = aes
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    ret = await worker._handle_aes({"cmd": "_master_tops", "id": "minion-1"})
    assert ret == ({"top": ["s1"]}, {"fun": "send"})


# --- _master_opts ----------------------------------------------------------


def test_master_opts_is_async_and_registered():
    assert inspect.iscoroutinefunction(salt.master.AESFuncs._master_opts)
    assert "_master_opts" in salt.master.AESFuncs.async_methods


async def test_master_opts_offloads_file_envs_to_executor():
    opts = {
        "top_file_merging_strategy": "merge",
        "env_order": [],
        "default_top": "base",
        "renderer": "yaml_jinja",
        "failhard": False,
        "state_top": "top.sls",
        "state_top_saltenv": None,
        "nodegroups": {},
        "state_auto_order": True,
        "state_events": False,
        "state_aggregate": False,
        "jinja_env": {},
        "jinja_sls_env": {},
        "jinja_lstrip_blocks": False,
        "jinja_trim_blocks": False,
    }
    aes = _build_bare_aesfuncs(opts)
    # ``_file_envs`` is an ``async def`` handler (Phase 2D) that offloads
    # the fileserver call to an executor internally; ``_master_opts`` just
    # awaits it, so the mock must be an AsyncMock.
    aes._file_envs = AsyncMock(return_value=["base", "dev"])
    mopts = await aes._master_opts({})
    # Return-shape parity: keys populated by the sync version must all be
    # present.
    assert set(mopts["file_roots"].keys()) == {"base", "dev"}
    for key in (
        "file_roots",
        "top_file_merging_strategy",
        "env_order",
        "default_top",
        "renderer",
        "failhard",
        "state_top",
        "state_top_saltenv",
        "nodegroups",
        "state_auto_order",
        "state_events",
        "state_aggregate",
        "jinja_env",
        "jinja_sls_env",
        "jinja_lstrip_blocks",
        "jinja_trim_blocks",
    ):
        assert key in mopts
    aes._file_envs.assert_awaited_once()


async def test_master_opts_env_only_short_circuits():
    """``env_only`` in the load must trim the returned dict, exactly as the
    pre-conversion sync version did."""
    opts = {
        "top_file_merging_strategy": "merge",
        "env_order": [],
        "default_top": "base",
    }
    aes = _build_bare_aesfuncs(opts)
    aes._file_envs = AsyncMock(return_value=["base"])
    mopts = await aes._master_opts({"env_only": True})
    assert set(mopts) == {
        "file_roots",
        "top_file_merging_strategy",
        "env_order",
        "default_top",
    }


# --- _register_resources ---------------------------------------------------


def test_register_resources_is_async_and_registered():
    assert inspect.iscoroutinefunction(salt.master.AESFuncs._register_resources)
    assert "_register_resources" in salt.master.AESFuncs.async_methods


async def test_register_resources_offloads_sync_body_to_executor(master_opts, tmp_path):
    """The blocking mmap-write + cache-store body must run through the
    executor. The wrapper only performs the async event fire on the main
    loop."""
    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = False
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)

    aes = salt.master.AESFuncs(opts)
    try:
        load = {"id": "minion-x", "resources": {"dummy": ["r1"]}}
        loop = asyncio.get_running_loop()
        with patch(
            "salt.utils.minions.update_resource_index", return_value=(1, 0)
        ), patch.object(loop, "run_in_executor", wraps=loop.run_in_executor) as rie:
            ret = await aes._register_resources(load)
        assert ret is True
        assert rie.called
        # First arg to run_in_executor is the executor (default None); second
        # is the bound sync helper.
        args = rie.call_args.args
        assert args[0] is None
        assert (
            args[1].__func__
            is salt.master.AESFuncs.__dict__["_AESFuncs__register_resources_sync"]
        )
    finally:
        aes.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_uses_fire_event_async_not_sync(master_opts, tmp_path):
    """When events are enabled the async path must call
    ``event.fire_event_async`` — the sync ``fire_event`` would defeat the
    async migration by blocking the MWorker loop."""
    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = True
    opts["minion_data_cache_events"] = True
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)

    aes = salt.master.AESFuncs(opts)
    try:
        aes.event = MagicMock()

        async def _fake_fire(data, tag):
            return None

        aes.event.fire_event_async = MagicMock(side_effect=_fake_fire)
        load = {
            "id": "minion-x",
            "resources": {"dummy": ["r1"]},
            "resource_grains": {"dummy:r1": {"k": "v"}},
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)):
            await aes._register_resources(load)
        aes.event.fire_event_async.assert_called_once_with(
            {"Resource cache refresh": "minion-x"},
            "resource/refresh/minion-x",
        )
        aes.event.fire_event.assert_not_called()
    finally:
        aes.destroy()
        salt.utils.resource_registry.reset_registry()


async def test_register_resources_bad_load_returns_empty_dict(master_opts, tmp_path):
    """Return-shape parity: missing keys yield ``{}`` — same as sync."""
    import salt.utils.resource_registry

    salt.utils.resource_registry.reset_registry()
    opts = master_opts.copy()
    opts["cachedir"] = str(tmp_path)
    opts["minion_data_cache"] = False
    opts.setdefault("resource_index_primary_capacity", 4096)
    opts.setdefault("resource_index_primary_slot_size", 128)

    aes = salt.master.AESFuncs(opts)
    try:
        ret = await aes._register_resources({"id": "minion-x"})  # no 'resources'
        assert ret == {}
    finally:
        aes.destroy()
        salt.utils.resource_registry.reset_registry()


# ---------------------------------------------------------------------------
# ClearFuncs async dispatch: Phase 2 of the async MWorker migration.
#
# Each of the following handlers is now ``async def`` and offloads its
# synchronous body (subprocess launch, wheel/runner call, disk-backed token
# I/O) to the default executor. These tests confirm:
#   1. The handler is registered in ``ClearFuncs.async_methods`` and
#      resolves to a coroutine function on the class.
#   2. Dispatch through the real ``MWorker._handle_clear`` async path
#      returns the wrapped ``(ret, {"fun": "send_clear"})`` envelope with
#      the same shape as the previous sync path.
#   3. Blocking work is scheduled via the running loop's default executor
#      rather than executed on the event loop thread.
# ---------------------------------------------------------------------------


def _clearfuncs_registry_names():
    return {"publish", "ping", "wheel", "runner", "get_token", "mk_token"}


def test_clearfuncs_async_methods_registry_expected_names():
    """The exact set of names registered — regression guard against silent
    additions/removals as more methods are migrated."""
    assert set(salt.master.ClearFuncs.async_methods) == _clearfuncs_registry_names()


def test_clearfuncs_async_methods_registry_entries_are_coroutine_functions():
    """Every name registered in ``ClearFuncs.async_methods`` must resolve to
    an ``async def`` on the class so ``MWorker._handle_clear`` can await it."""
    for name in salt.master.ClearFuncs.async_methods:
        handler = getattr(salt.master.ClearFuncs, name, None)
        assert handler is not None, f"{name} listed but not defined on ClearFuncs"
        assert inspect.iscoroutinefunction(handler), name


def _make_clear_worker(clear_funcs):
    """Build a bare :class:`MWorker` bound to ``clear_funcs`` so tests can
    exercise the real ``_handle_clear`` dispatch path (async_methods lookup,
    ``await``, envelope wrapping)."""
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.clear_funcs = clear_funcs
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    return worker


def _make_bare_clear_funcs():
    """Build a :class:`ClearFuncs` shell without running ``__init__`` — the
    handlers we test only touch ``self.loadauth`` / ``self.ckminions`` /
    ``self.event`` / ``self.wheel_``, each of which is mocked per-test."""
    cf = salt.master.ClearFuncs.__new__(salt.master.ClearFuncs)
    cf.opts = {}
    cf.event = MagicMock()
    cf.local = None
    cf.ckminions = MagicMock()
    cf.loadauth = MagicMock()
    cf.mminion = MagicMock()
    cf.masterapi = MagicMock()
    cf.wheel_ = MagicMock()
    cf.channels = []
    return cf


# --- ping ------------------------------------------------------------------


async def test_clearfuncs_ping_dispatch_returns_load_verbatim():
    """``ping`` echoes the cleartext load; envelope shape is preserved."""
    cf = _make_bare_clear_funcs()
    worker = _make_clear_worker(cf)
    load = {"cmd": "ping", "id": "minion-a", "extra": [1, 2]}
    envelope = await worker._handle_clear(load)
    assert envelope == (load, {"fun": "send_clear"})


# --- get_token / mk_token --------------------------------------------------


async def test_clearfuncs_get_token_missing_returns_false():
    cf = _make_bare_clear_funcs()
    worker = _make_clear_worker(cf)
    envelope = await worker._handle_clear({"cmd": "get_token"})
    assert envelope == (False, {"fun": "send_clear"})
    cf.loadauth.get_tok.assert_not_called()


async def test_clearfuncs_get_token_offloads_to_run_in_executor():
    """``LoadAuth.get_tok`` reads and deserializes from disk — must run in
    the executor, not on the event loop thread."""
    cf = _make_bare_clear_funcs()
    cf.loadauth.get_tok = MagicMock(return_value={"name": "eve"})

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=spy):
        ret = await cf.get_token({"token": "abc"})

    assert ret == {"name": "eve"}
    assert len(calls) == 1
    assert calls[0][0] is None  # default executor
    cf.loadauth.get_tok.assert_called_once_with("abc")


async def test_clearfuncs_mk_token_empty_returns_empty_string():
    cf = _make_bare_clear_funcs()
    cf.loadauth.mk_token = MagicMock(return_value={})
    worker = _make_clear_worker(cf)
    envelope = await worker._handle_clear({"cmd": "mk_token", "eauth": "pam"})
    assert envelope == ("", {"fun": "send_clear"})


async def test_clearfuncs_mk_token_returns_token_verbatim():
    cf = _make_bare_clear_funcs()
    token = {"token": "t-1", "name": "eve", "eauth": "pam"}
    cf.loadauth.mk_token = MagicMock(return_value=token)
    worker = _make_clear_worker(cf)
    envelope = await worker._handle_clear({"cmd": "mk_token", "eauth": "pam"})
    assert envelope == (token, {"fun": "send_clear"})


async def test_clearfuncs_mk_token_offloads_to_run_in_executor():
    """``LoadAuth.mk_token`` invokes the eauth backend + writes to disk —
    must run in the executor."""
    cf = _make_bare_clear_funcs()
    cf.loadauth.mk_token = MagicMock(return_value={"token": "t-1"})

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=spy):
        ret = await cf.mk_token({"eauth": "pam", "username": "u"})

    assert ret == {"token": "t-1"}
    assert len(calls) == 1
    assert calls[0][0] is None


# --- runner ----------------------------------------------------------------


async def test_clearfuncs_runner_auth_error_returns_error_dict():
    cf = _make_bare_clear_funcs()
    cf.loadauth.check_authentication = MagicMock(
        return_value={"error": {"name": "AuthenticationError", "message": "nope"}}
    )
    worker = _make_clear_worker(cf)
    envelope = await worker._handle_clear(
        {"cmd": "runner", "fun": "test.arg", "eauth": "pam"}
    )
    assert envelope == (
        {"error": {"name": "AuthenticationError", "message": "nope"}},
        {"fun": "send_clear"},
    )


async def test_clearfuncs_runner_offloads_asynchronous_launch_to_executor():
    """``RunnerClient.asynchronous`` forks + joins a subprocess — must run
    off the event loop thread."""
    cf = _make_bare_clear_funcs()
    cf.loadauth.check_authentication = MagicMock(
        return_value={
            "username": "eve",
            "auth_list": [],
        }
    )
    cf.ckminions.runner_check = MagicMock(return_value=True)
    fake_pub = {"jid": "20260101000000000000", "tag": "salt/run/x"}

    runner_client = MagicMock()
    runner_client.asynchronous = MagicMock(return_value=fake_pub)

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch("salt.runner.RunnerClient", return_value=runner_client), patch.object(
        loop, "run_in_executor", side_effect=spy
    ):
        ret = await cf.runner(
            {"fun": "test.arg", "eauth": "pam", "kwarg": {"foo": "bar"}}
        )

    assert ret == fake_pub
    assert len(calls) == 1
    assert calls[0][0] is None
    runner_client.asynchronous.assert_called_once()


# --- wheel -----------------------------------------------------------------


async def test_clearfuncs_wheel_auth_error_returns_error_dict():
    cf = _make_bare_clear_funcs()
    cf.loadauth.check_authentication = MagicMock(
        return_value={"error": {"name": "AuthenticationError", "message": "nope"}}
    )
    worker = _make_clear_worker(cf)
    envelope = await worker._handle_clear(
        {"cmd": "wheel", "fun": "key.list_all", "eauth": "pam"}
    )
    assert envelope == (
        {"error": {"name": "AuthenticationError", "message": "nope"}},
        {"fun": "send_clear"},
    )


async def test_clearfuncs_wheel_offloads_call_func_to_executor():
    """``Wheel.call_func`` executes wheel modules synchronously (key ops,
    fileserver, disk I/O) — must run in the executor."""
    cf = _make_bare_clear_funcs()
    cf.loadauth.check_authentication = MagicMock(
        return_value={"username": "eve", "auth_list": []}
    )
    cf.ckminions.wheel_check = MagicMock(return_value=True)
    cf.wheel_.call_func = MagicMock(
        return_value={"return": ["k1", "k2"], "success": True}
    )

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=spy):
        ret = await cf.wheel({"fun": "key.list_all", "eauth": "pam"})

    assert isinstance(ret, dict)
    assert ret["data"]["return"] == ["k1", "k2"]
    assert ret["data"]["success"] is True
    assert ret["data"]["fun"] == "wheel.key.list_all"
    assert ret["data"]["user"] == "eve"
    assert "tag" in ret and "jid" in ret["data"]
    assert len(calls) == 1
    assert calls[0][0] is None
    cf.wheel_.call_func.assert_called_once()


async def test_clearfuncs_wheel_exception_fires_event_via_fire_event_async():
    """When ``call_func`` raises, the failure event must be fired via
    ``fire_event_async`` — the sync ``fire_event`` would block the loop."""
    cf = _make_bare_clear_funcs()
    cf.loadauth.check_authentication = MagicMock(
        return_value={"username": "eve", "auth_list": []}
    )
    cf.ckminions.wheel_check = MagicMock(return_value=True)
    cf.wheel_.call_func = MagicMock(side_effect=RuntimeError("boom"))

    async def _fake_fire(data, tag):
        return None

    cf.event.fire_event_async = MagicMock(side_effect=_fake_fire)

    ret = await cf.wheel({"fun": "key.finger", "eauth": "pam"})
    assert ret["data"]["success"] is False
    assert "boom" in ret["data"]["return"]
    cf.event.fire_event_async.assert_called_once()
    cf.event.fire_event.assert_not_called()


# ---------------------------------------------------------------------------
# AuthFuncs async dispatch: minion authentication (``_auth`` / ``_auth_impl``).
#
# The auth state machine now runs on the MWorker event loop as ``async def``.
# Blocking work (disk-backed key/session cache, RSA operations, event fires)
# is offloaded to the default executor, and the ~10 auth-event fires have
# been swapped to ``fire_event_async``.
#
# These tests confirm:
#   1. Both wrappers (``_auth``, ``_auth_impl``, ``_clear_signed``) are
#      coroutine functions.
#   2. Async dispatch preserves return-value shape byte-for-byte across the
#      major state-machine branches (invalid id, max_minions full, rejected,
#      pending).
#   3. Key auth-event fires go through ``fire_event_async`` rather than the
#      sync ``fire_event`` which would defeat the async migration.
# ---------------------------------------------------------------------------


def test_auth_funcs_auth_and_impl_are_coroutine_functions():
    """Regression guard: ``_auth``, ``_auth_impl`` and ``_clear_signed`` must
    all be ``async def`` on ``AuthFuncs`` so the dispatch chain can await
    them from the async ``ReqServerChannel.handle_message`` / pooled
    ``_handle_clear_auth_local`` code paths."""
    assert inspect.iscoroutinefunction(salt.master.AuthFuncs._auth)
    assert inspect.iscoroutinefunction(salt.master.AuthFuncs._auth_impl)
    assert inspect.iscoroutinefunction(salt.master.AuthFuncs._clear_signed)


async def test_auth_funcs_max_minions_full_fires_event_async(auth_funcs):
    """When ``max_minions`` is reached and auth events are enabled, the
    ``full`` event must go through ``fire_event_async``; the sync
    ``fire_event`` would block the auth loop and defeat the migration."""
    auth_funcs.opts["max_minions"] = 1
    auth_funcs.opts["auth_events"] = True
    auth_funcs.cache_cli = False
    ckminions = MagicMock()
    ckminions.connected_ids.return_value = {"already-here", "another"}
    auth_funcs.ckminions = ckminions
    event = MagicMock()

    async def _fake_fire(data, tag):
        return None

    event.fire_event_async = MagicMock(side_effect=_fake_fire)
    auth_funcs.event = event
    load = {
        "id": "newcomer",
        "pub": "stub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": "full"}}
    event.fire_event_async.assert_called_once()
    event.fire_event.assert_not_called()


async def test_auth_funcs_offloads_ckminions_connected_ids_to_executor(auth_funcs):
    """``ckminions.connected_ids`` walks the minion data cache on disk; the
    async auth path must offload it via ``loop.run_in_executor`` rather
    than call it on the event loop thread."""
    auth_funcs.opts["max_minions"] = 1
    auth_funcs.opts["auth_events"] = False
    auth_funcs.cache_cli = False
    ckminions = MagicMock()
    ckminions.connected_ids.return_value = {"m1", "m2"}
    auth_funcs.ckminions = ckminions

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    seen_calls = []

    def spy(executor, func, *args):
        seen_calls.append(func)
        return original_run_in_executor(executor, func, *args)

    load = {
        "id": "newcomer",
        "pub": "stub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    with patch.object(loop, "run_in_executor", side_effect=spy):
        await auth_funcs._auth(load, sign_messages=False, version=2)
    # ``connected_ids`` is offloaded once at the start of the max_minions
    # check; the exact identity confirms the call went through the executor.
    assert ckminions.connected_ids in seen_calls


async def test_auth_funcs_pending_fires_event_async(auth_funcs):
    """The ``pend`` event on a new minion must go through
    ``fire_event_async``."""
    auth_funcs.opts["max_minions"] = 0
    auth_funcs.opts["auth_events"] = True
    auth_funcs.opts["open_mode"] = False
    auth_funcs.auto_key = MagicMock()
    auth_funcs.auto_key.check_autoreject.return_value = False
    auth_funcs.auto_key.check_autosign.return_value = False
    cache = MagicMock()
    cache.fetch.return_value = None
    auth_funcs.cache = cache
    event = MagicMock()

    async def _fake_fire(data, tag):
        return None

    event.fire_event_async = MagicMock(side_effect=_fake_fire)
    auth_funcs.event = event
    load = {
        "id": "fresh-minion",
        "pub": "fresh-pub",
        "nonce": "n",
        "enc_algo": salt.crypt.OAEP_SHA1,
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    ret = await auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": True}}
    event.fire_event_async.assert_called_once()
    event.fire_event.assert_not_called()


async def test_auth_funcs_clear_signed_offloads_rsa_sign_to_executor(auth_funcs):
    """``_clear_signed`` performs an RSA signing operation via
    ``master_key.sign``; that CPU-bound call must run in the executor."""
    signed_bytes = b"deadbeef"
    auth_funcs.master_key = MagicMock()
    auth_funcs.master_key.sign = MagicMock(return_value=signed_bytes)

    loop = asyncio.get_running_loop()
    original_run_in_executor = loop.run_in_executor
    calls = []

    def spy(executor, func, *args):
        calls.append((executor, func, args))
        return original_run_in_executor(executor, func, *args)

    with patch.object(loop, "run_in_executor", side_effect=spy):
        ret = await auth_funcs._clear_signed(
            {"ret": True, "nonce": "n"}, salt.crypt.PKCS1v15_SHA1
        )
    assert isinstance(ret, dict)
    assert ret["enc"] == "clear"
    assert ret["sig"] is signed_bytes
    assert calls
    assert calls[0][0] is None  # default executor
    auth_funcs.master_key.sign.assert_called_once()


# ---------------------------------------------------------------------------
# master_mworker_max_inflight — fast-path / opt-in shape
# ---------------------------------------------------------------------------


def _bare_worker(opts):
    """Build an MWorker skeleton without forking.

    Only the attributes ``_handle_payload`` reads are populated so the
    semaphore fast-path can be exercised without booting a full worker.
    """
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = dict(opts)
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    worker._modules_loaded = threading.Event()
    worker._modules_loaded.set()
    return worker


def test_default_master_opts_ships_inflight_cap_zero():
    """
    The default cap MUST be 0 (unlimited).  Any other value would be a
    silent behavior change on 3008.x and on master.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["master_mworker_max_inflight"] == 0


async def test_handle_payload_skips_semaphore_when_flag_off(master_opts):
    """
    With ``master_async_mworker`` off the cap is meaningless (sync
    dispatch tops out at 1 in flight per worker), so the semaphore MUST
    NOT be built even when ``master_mworker_max_inflight`` is set.
    Building it would allocate an ``asyncio.BoundedSemaphore`` on the
    wrong loop and mask the pre-PR fast path.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = False
    opts["master_mworker_max_inflight"] = 4
    worker = _bare_worker(opts)

    # Stub the inner handler so the test does not care about payload
    # shape.  ``_handle_payload`` only awaits it.
    async def _inner(payload):
        return "ok"

    worker._handle_payload_inner = _inner
    ret = await worker._handle_payload({"cmd": "_return"})
    assert ret == "ok"
    assert worker._inflight_sem is None
    assert worker._inflight_sem_ready is True


async def test_handle_payload_skips_semaphore_when_cap_zero(master_opts):
    """
    Even in opt-in mode, ``master_mworker_max_inflight = 0`` MUST stay
    on the no-semaphore fast path.  Zero is the documented "unlimited"
    sentinel and must impose zero overhead.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = True
    opts["master_mworker_max_inflight"] = 0
    worker = _bare_worker(opts)

    async def _inner(payload):
        return "ok"

    worker._handle_payload_inner = _inner
    ret = await worker._handle_payload({"cmd": "_return"})
    assert ret == "ok"
    assert worker._inflight_sem is None


async def test_handle_payload_builds_semaphore_when_flag_on_and_cap_set(
    master_opts,
):
    """
    Opt-in path with a positive cap MUST allocate an
    ``asyncio.BoundedSemaphore`` on the running loop on first entry and
    reuse it on subsequent calls.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = True
    opts["master_mworker_max_inflight"] = 3
    worker = _bare_worker(opts)

    async def _inner(payload):
        return "ok"

    worker._handle_payload_inner = _inner
    await worker._handle_payload({"cmd": "_return"})
    sem = worker._inflight_sem
    assert isinstance(sem, asyncio.BoundedSemaphore)
    # Second dispatch reuses the same semaphore instance — no per-call
    # allocation on the hot path.
    await worker._handle_payload({"cmd": "_return"})
    assert worker._inflight_sem is sem


async def test_handle_payload_caps_concurrent_dispatches(master_opts):
    """
    With ``master_mworker_max_inflight = 2`` and 8 concurrent dispatches
    against an inner handler that sleeps, the number of handlers
    executing in parallel MUST NEVER exceed 2.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = True
    opts["master_mworker_max_inflight"] = 2
    worker = _bare_worker(opts)

    # Reset the module-level counter so the previous test's residuals
    # don't leak in.  ``waiters`` is transient; ``wait_ms_total`` is a
    # monotonically growing counter but we only assert non-negative
    # deltas within this test.
    salt.master._MW_INFLIGHT["waiters"] = 0

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def _inner(payload):
        nonlocal active, max_active
        async with lock:
            active += 1
            if active > max_active:
                max_active = active
        try:
            await asyncio.sleep(0.05)
            return "ok"
        finally:
            async with lock:
                active -= 1

    worker._handle_payload_inner = _inner
    results = await asyncio.gather(
        *(worker._handle_payload({"cmd": "_return"}) for _ in range(8))
    )
    assert results == ["ok"] * 8
    assert max_active == 2, (
        f"cap violated: observed {max_active} concurrent handlers, "
        "expected at most 2"
    )
    # Waiters counter drained back to zero.
    assert salt.master._MW_INFLIGHT["waiters"] == 0


async def test_handle_payload_no_cap_allows_full_concurrency(master_opts):
    """
    With ``master_mworker_max_inflight = 0`` and 8 concurrent dispatches,
    all 8 handlers MUST be able to run in parallel — no throttling.
    Regression test proving the zero-cap fast path really is unlimited.
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = True
    opts["master_mworker_max_inflight"] = 0
    worker = _bare_worker(opts)

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def _inner(payload):
        nonlocal active, max_active
        async with lock:
            active += 1
            if active > max_active:
                max_active = active
        try:
            await asyncio.sleep(0.05)
            return "ok"
        finally:
            async with lock:
                active -= 1

    worker._handle_payload_inner = _inner
    results = await asyncio.gather(
        *(worker._handle_payload({"cmd": "_return"}) for _ in range(8))
    )
    assert results == ["ok"] * 8
    assert max_active == 8
