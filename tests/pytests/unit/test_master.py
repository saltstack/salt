# pylint: skip-file
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
from tests.support.mock import MagicMock, patch
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
    The Master's ClearFuncs object
    """
    clear_funcs = salt.master.ClearFuncs(master_opts, {})
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
def test_when_syndic_return_processes_load_then_correct_values_should_be_returned(
    expected_return, payload, encrypted_requests
):
    with patch.object(encrypted_requests, "_return", autospec=True) as fake_return:
        encrypted_requests._syndic_return(payload)
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
        "_handle_minion_event",
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


def test_syndic_return_cache_dir_creation(encrypted_requests):
    """master's cachedir for a syndic will be created by AESFuncs._syndic_return method"""
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert (cachedir / "syndics").exists()
    assert (cachedir / "syndics" / "mamajama").exists()


def test_syndic_return_cache_dir_creation_traversal(encrypted_requests):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "../mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert not (cachedir / "syndics").exists()
    assert not (cachedir / "mamajama").exists()


def test_pub_ret_traversal(encrypted_requests, tmp_path):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    priv, pub = salt.crypt.gen_keys(2048)

    minions = pathlib.Path(encrypted_requests.opts["pki_dir"]) / "minions"
    minions.mkdir()

    with salt.utils.files.fopen(minions / "minion", "w") as wfp:
        wfp.write(pub)

    with pytest.raises(salt.exceptions.SaltValidationError):
        encrypted_requests.pub_ret(
            {
                "tok": salt.crypt.PrivateKey.from_str(priv).encrypt(b"salt"),
                "id": "minion",
                "jid": "asdf/../../../sdf",
                "return": {},
            }
        )


def test_return_signature_verifies_after_channel_packaging(tmp_path, caplog):
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
        ret = aes_funcs._return(inner_load)

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
def test_on_demand_allowed_command_injection(allowed_funcs, tmp_path, caplog):
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
        ret = allowed_funcs._pillar(load)
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


def test_on_demand_not_allowed(not_allowed_funcs, tmp_path, caplog):
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
        ret = not_allowed_funcs._pillar(load)
    assert not pwnpath.exists()
    assert (
        "The following ext_pillar modules are not allowed for on-demand pillar data: git."
        in caplog.text
    )


def test_register_resources_updates_resource_index_when_minion_data_cache_disabled(
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
            aes_funcs._register_resources(load)
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


def test_register_resources_persists_resource_grains_to_cache(master_opts, tmp_path):
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
            aes_funcs._register_resources(load)
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


def test_register_resources_flushes_dropped_resource_grain_entry(master_opts, tmp_path):
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
        aes_funcs._register_resources(load1)
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
        aes_funcs._register_resources(load2)
        # The flush must remove the orphaned SRN.
        remaining = sorted(cache.list("resource_grains") or [])
        assert remaining == ["dummy:m2-d1"]
        # And the surviving entry must reflect the most recent payload.
        assert cache.fetch("resource_grains", "dummy:m2-d1") == {"k": "v1-updated"}
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


def test_register_resources_does_not_flush_srn_owned_by_other_minion(
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
        aes_funcs._register_resources(
            {
                "id": "minion-A",
                "resources": {"dummy": ["shared"]},
                "resource_grains": {"dummy:shared": {"who": "A"}},
            }
        )
        # minion-B claims dummy:shared (registry overwrites the SRN's owner).
        aes_funcs._register_resources(
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
        aes_funcs._register_resources(
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


def test_register_resources_resource_grains_visible_across_aes_funcs_instances(
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
        aes_funcs_a._register_resources(
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


def test_register_resources_fires_minion_data_cache_event(master_opts, tmp_path):
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
    try:
        load = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1"]},
            "resource_grains": {"dummy:m2-d1": {"k": "v1"}},
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)):
            aes_funcs._register_resources(load)
        # ``_pillar`` fires ``minion/refresh/<id>`` for grain refreshes (see
        # the analogous ``tagify(load["id"], "refresh", "minion")`` call);
        # the resource registration path mirrors that with ``resource`` as
        # the namespace, yielding ``resource/refresh/<id>``.
        aes_funcs.event.fire_event.assert_called_once_with(
            {"Resource cache refresh": "minion-2"},
            "resource/refresh/minion-2",
        )
    finally:
        aes_funcs.destroy()
        salt.utils.resource_registry.reset_registry()


def test_register_resources_does_not_fire_event_when_events_disabled(
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
    try:
        load = {
            "id": "minion-2",
            "resources": {"dummy": ["m2-d1"]},
            "resource_grains": {"dummy:m2-d1": {"k": "v1"}},
        }
        with patch("salt.utils.minions.update_resource_index", return_value=(1, 0)):
            aes_funcs._register_resources(load)
        aes_funcs.event.fire_event.assert_not_called()
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


def test_auth_funcs_rejects_invalid_id(auth_funcs):
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
    ret = auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": False}}
    auth_funcs.cache.fetch.assert_not_called()
    auth_funcs.event.fire_event.assert_not_called()


def test_auth_funcs_rejects_when_max_minions_full(auth_funcs):
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
    ret = auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": "full"}}
    auth_funcs.cache.store.assert_not_called()


def test_auth_funcs_rejected_key_state(auth_funcs):
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
    ret = auth_funcs._auth(load, sign_messages=False, version=2)
    assert ret == {"enc": "clear", "load": {"ret": False}}
    cache.store.assert_not_called()


def test_auth_funcs_pending_when_new_minion(auth_funcs):
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
    ret = auth_funcs._auth(load, sign_messages=False, version=2)
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
                aes._register_resources(
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
