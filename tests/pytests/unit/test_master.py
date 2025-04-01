import os
import pathlib
import stat
import threading
import time

import pytest

import salt.master
import salt.utils.platform
from tests.support.mock import MagicMock, patch


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
    return salt.master.AESFuncs(
        opts={
            "cachedir": str(tmp_path / "cache"),
            "sock_dir": str(tmp_path / "sock_drawer"),
            "conf_file": str(tmp_path / "config.conf"),
            "fileserver_backend": "local",
            "master_job_cache": False,
        }
    )


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
