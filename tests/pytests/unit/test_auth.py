import time

import pytest

import salt.auth
import salt.config
import salt.exceptions
import salt.master
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def load_auth():
    patches = (
        (
            "salt.loader.auth",
            MagicMock(
                return_value={
                    "pam.auth": "fake_func_str",
                    "pam.groups": "fake_groups_function_str",
                }
            ),
        ),
        (
            "salt.loader.eauth_tokens",
            MagicMock(
                return_value={
                    "localfs.mk_token": "fake_func_mktok",
                    "localfs.get_token": "fake_func_gettok",
                    "localfs.rm_roken": "fake_func_rmtok",
                }
            ),
        ),
    )
    patchers = []
    for mod, mock in patches:
        patcher = patch(mod, mock)
        patcher.start()
        patchers.append(patcher)
    lauth = salt.auth.LoadAuth({})  # Load with empty opts
    try:
        yield lauth
    finally:
        for patcher in patchers:
            patcher.stop()


@pytest.fixture
def master_acl_master_opts(master_opts):
    master_opts["publisher_acl"] = {}
    master_opts["publisher_acl_blacklist"] = {}
    master_opts["master_job_cache"] = ""
    master_opts["sign_pub_messages"] = False
    master_opts["con_cache"] = ""
    master_opts["external_auth"] = {}
    master_opts["external_auth"]["pam"] = {
        "test_user": [
            {"*": ["test.ping"]},
            {"minion_glob*": ["foo.bar"]},
            {"minion_func_test": ["func_test.*"]},
        ],
        "test_group%": [{"*": ["test.echo"]}],
        "test_user_mminion": [{"target_minion": ["test.ping"]}],
        "*": [{"my_minion": ["my_mod.my_func"]}],
        "test_user_func": [
            {
                "*": [
                    {"test.echo": {"args": ["MSG:.*"]}},
                    {
                        "test.echo": {
                            "kwargs": {
                                "text": "KWMSG:.*",
                                "anything": ".*",
                                "none": None,
                            }
                        }
                    },
                    {
                        "my_mod.*": {
                            "args": ["a.*", "b.*"],
                            "kwargs": {"kwa": "kwa.*", "kwb": "kwb"},
                        }
                    },
                ]
            },
            {
                "minion1": [
                    {"test.echo": {"args": ["TEST", None, "TEST.*"]}},
                    {"test.empty": {}},
                ]
            },
        ],
    }
    yield master_opts


@pytest.fixture
def master_acl_clear_funcs(master_acl_master_opts):
    fire_event_mock = MagicMock(return_value="dummy_tag")
    patches = (
        ("zmq.Context", MagicMock()),
        ("salt.payload.dumps", MagicMock()),
        ("salt.master.tagify", MagicMock()),
        ("salt.utils.event.SaltEvent.fire_event", fire_event_mock),
        ("salt.auth.LoadAuth.time_auth", MagicMock(return_value=True)),
        ("salt.minion.MasterMinion", MagicMock()),
        ("salt.utils.verify.check_path_traversal", MagicMock()),
        ("salt.client.get_local_client", MagicMock()),
    )
    patchers = []
    for mod, mock in patches:
        patcher = patch(mod, mock)
        patcher.start()
        patchers.append(patcher)
    clear = salt.master.ClearFuncs(master_acl_master_opts, MagicMock())

    async def _send_pub(*args):
        pass

    clear._send_pub = _send_pub
    try:
        yield clear
    finally:
        for patcher in patchers:
            patcher.stop()


@pytest.fixture
def master_acl_valid_load():
    yield {
        "tgt_type": "glob",
        "jid": "",
        "cmd": "publish",
        "tgt": "test_minion",
        "kwargs": {
            "username": "test_user",
            "password": "test_password",
            "show_timeout": False,
            "eauth": "pam",
            "show_jid": False,
        },
        "ret": "",
        "user": "test_user",
        "key": "",
        "arg": "",
        "fun": "test.ping",
    }


@pytest.fixture
def auth_acl_master_opts(master_opts):
    """
    Master options
    """
    master_opts["publisher_acl"] = {}
    master_opts["publisher_acl_blacklist"] = {}
    master_opts["master_job_cache"] = ""
    master_opts["sign_pub_messages"] = False
    master_opts["con_cache"] = ""
    master_opts["external_auth"] = {}
    master_opts["external_auth"] = {
        "pam": {"test_user": [{"alpha_minion": ["test.ping"]}]}
    }
    yield master_opts


@pytest.fixture
def auth_acl_clear_funcs(auth_acl_master_opts):
    auth_check_mock = MagicMock(return_value=True)
    patches = (
        ("salt.minion.MasterMinion", MagicMock()),
        ("salt.utils.verify.check_path_traversal", MagicMock()),
        ("salt.utils.minions.CkMinions.auth_check", auth_check_mock),
        ("salt.auth.LoadAuth.time_auth", MagicMock(return_value=True)),
        ("salt.client.get_local_client", MagicMock()),
    )
    patchers = []
    for mod, mock in patches:
        patcher = patch(mod, mock)
        patcher.start()
        patchers.append(patcher)
    clear = salt.master.ClearFuncs(auth_acl_master_opts, MagicMock())
    try:
        yield clear
    finally:
        for patcher in patchers:
            patcher.stop()


@pytest.fixture
def auth_acl_valid_load():
    yield {
        "tgt_type": "glob",
        "jid": "",
        "cmd": "publish",
        "tgt": "test_minion",
        "kwargs": {
            "username": "test_user",
            "password": "test_password",
            "show_timeout": False,
            "eauth": "pam",
            "show_jid": False,
        },
        "ret": "",
        "user": "test_user",
        "key": "",
        "arg": "",
        "fun": "test.ping",
    }


def test_get_tok_with_broken_file_will_remove_bad_token(load_auth):
    fake_get_token = MagicMock(
        side_effect=salt.exceptions.SaltDeserializationError("hi")
    )
    patch_opts = patch.dict(load_auth.opts, {"eauth_tokens": "testfs"})
    patch_get_token = patch.dict(
        load_auth.tokens,
        {"testfs.get_token": fake_get_token},
    )
    mock_rm_token = MagicMock()
    patch_rm_token = patch.object(load_auth, "rm_token", mock_rm_token)
    with patch_opts, patch_get_token, patch_rm_token:
        expected_token = "fnord"
        load_auth.get_tok(expected_token)
        mock_rm_token.assert_called_with(expected_token)


def test_get_tok_with_no_expiration_should_remove_bad_token(load_auth):
    fake_get_token = MagicMock(return_value={"no_expire_here": "Nope"})
    patch_opts = patch.dict(load_auth.opts, {"eauth_tokens": "testfs"})
    patch_get_token = patch.dict(
        load_auth.tokens,
        {"testfs.get_token": fake_get_token},
    )
    mock_rm_token = MagicMock()
    patch_rm_token = patch.object(load_auth, "rm_token", mock_rm_token)
    with patch_opts, patch_get_token, patch_rm_token:
        expected_token = "fnord"
        load_auth.get_tok(expected_token)
        mock_rm_token.assert_called_with(expected_token)


def test_get_tok_with_expire_before_current_time_should_remove_token(load_auth):
    fake_get_token = MagicMock(return_value={"expire": time.time() - 1})
    patch_opts = patch.dict(load_auth.opts, {"eauth_tokens": "testfs"})
    patch_get_token = patch.dict(
        load_auth.tokens,
        {"testfs.get_token": fake_get_token},
    )
    mock_rm_token = MagicMock()
    patch_rm_token = patch.object(load_auth, "rm_token", mock_rm_token)
    with patch_opts, patch_get_token, patch_rm_token:
        expected_token = "fnord"
        load_auth.get_tok(expected_token)
        mock_rm_token.assert_called_with(expected_token)


def test_get_tok_with_valid_expiration_should_return_token(load_auth):
    expected_token = {"expire": time.time() + 1}
    fake_get_token = MagicMock(return_value=expected_token)
    patch_opts = patch.dict(load_auth.opts, {"eauth_tokens": "testfs"})
    patch_get_token = patch.dict(
        load_auth.tokens,
        {"testfs.get_token": fake_get_token},
    )
    mock_rm_token = MagicMock()
    patch_rm_token = patch.object(load_auth, "rm_token", mock_rm_token)
    with patch_opts, patch_get_token, patch_rm_token:
        token_name = "fnord"
        actual_token = load_auth.get_tok(token_name)
        mock_rm_token.assert_not_called()
        assert expected_token is actual_token, "Token was not returned"


def test_load_name(load_auth):
    valid_eauth_load = {
        "username": "test_user",
        "show_timeout": False,
        "test_password": "",
        "eauth": "pam",
    }

    # Test a case where the loader auth doesn't have the auth type
    without_auth_type = dict(valid_eauth_load)
    without_auth_type.pop("eauth")
    ret = load_auth.load_name(without_auth_type)
    assert ret == "", "Did not bail when the auth loader didn't have the auth type."

    # Test a case with valid params
    with patch(
        "salt.utils.args.arg_lookup",
        MagicMock(return_value={"args": ["username", "password"]}),
    ) as format_call_mock:
        expected_ret = call("fake_func_str")
        ret = load_auth.load_name(valid_eauth_load)
        format_call_mock.assert_has_calls((expected_ret,), any_order=True)
        assert ret == "test_user"


def test_get_groups(load_auth):
    valid_eauth_load = {
        "username": "test_user",
        "show_timeout": False,
        "test_password": "",
        "eauth": "pam",
    }
    with patch("salt.utils.args.format_call") as format_call_mock:
        expected_ret = call(
            "fake_groups_function_str",
            {
                "username": "test_user",
                "test_password": "",
                "show_timeout": False,
                "eauth": "pam",
            },
            expected_extra_kws=salt.auth.AUTH_INTERNAL_KEYWORDS,
        )
        load_auth.get_groups(valid_eauth_load)
        format_call_mock.assert_has_calls((expected_ret,), any_order=True)


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_master_publish_name(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test to ensure a simple name can auth against a given function.
    This tests to ensure test_user can access test.ping but *not* sys.doc
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        # Can we access test.ping?
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "test.ping"
        )

        # Are we denied access to sys.doc?
        sys_doc_load = master_acl_valid_load
        sys_doc_load["fun"] = "sys.doc"
        await master_acl_clear_funcs.publish(sys_doc_load)
        assert "error" in master_acl_clear_funcs.event.fire_event.call_args[0][0]


async def test_master_publish_group(master_acl_clear_funcs, master_acl_valid_load):
    """
    Tests to ensure test_group can access test.echo but *not* sys.doc
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"]["user"] = "new_user"
        master_acl_valid_load["fun"] = "test.echo"
        master_acl_valid_load["arg"] = "hello"
        with patch(
            "salt.auth.LoadAuth.get_groups",
            return_value=["test_group", "second_test_group"],
        ):
            await master_acl_clear_funcs.publish(master_acl_valid_load)
        # Did we fire test.echo?
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "test.echo"
        )

        # Request sys.doc
        master_acl_valid_load["fun"] = "sys.doc"

        # XXX: Of course we won't fire an event if publish isn't called. If
        # sys.dock is there when we publish is that a bug?

        # await master_acl_clear_funcs.publish(master_acl_valid_load)

        # Did we fire it?
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"] != "sys.doc"
        )


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_master_publish_some_minions(
    master_acl_clear_funcs, master_acl_valid_load
):
    """
    Tests to ensure we can only target minions for which we
    have permission with publisher acl.

    Note that in order for these sorts of tests to run correctly that
    you should NOT patch check_minions!
    """
    master_acl_valid_load["kwargs"]["username"] = "test_user_mminion"
    master_acl_valid_load["user"] = "test_user_mminion"
    await master_acl_clear_funcs.publish(master_acl_valid_load)
    assert master_acl_clear_funcs.event.fire_event.mock_calls == []


async def test_master_not_user_glob_all(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test to ensure that we DO NOT access to a given
    function to all users with publisher acl. ex:

    '*':
        my_minion:
            - my_func

    Yes, this seems like a bit of a no-op test but it's
    here to document that this functionality
    is NOT supported currently.

    WARNING: Do not patch this wit
    """
    master_acl_valid_load["kwargs"]["username"] = "NOT_A_VALID_USERNAME"
    master_acl_valid_load["user"] = "NOT_A_VALID_USERNAME"
    master_acl_valid_load["fun"] = "test.ping"
    await master_acl_clear_funcs.publish(master_acl_valid_load)
    assert "error" in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
    assert master_acl_clear_funcs.event.fire_event.mock_calls == []


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_master_minion_glob(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test to ensure we can allow access to a given
    function for a user to a subset of minions
    selected by a glob. ex:

    test_user:
        'minion_glob*':
          - glob_mod.glob_func

    This test is a bit tricky, because ultimately the real functionality
    lies in what's returned from check_minions, but this checks a limited
    amount of logic on the way there as well. Note the inline patch.
    """
    requested_function = "foo.bar"
    requested_tgt = "minion_glob1"
    master_acl_valid_load["tgt"] = requested_tgt
    master_acl_valid_load["fun"] = requested_function
    _check_minions_return = {"minions": ["minion_glob1"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):  # Assume that there is a listening minion match
        await master_acl_clear_funcs.publish(master_acl_valid_load)
    assert (
        master_acl_clear_funcs.event.fire_event.called is True
    ), f"Did not fire {requested_function} for minion tgt {requested_tgt}"
    assert (
        master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
        == requested_function
    ), f"Did not fire {requested_function} for minion glob"


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_args_empty_spec(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple arg restriction allowed.

    'test_user_func':
        minion1:
            - test.empty:
    """
    _check_minions_return = {"minions": ["minion1"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "minion1",
                "fun": "test.empty",
                "arg": ["TEST"],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "test.empty"
        )


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_args_simple_match(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple arg restriction allowed.

    'test_user_func':
        minion1:
            - test.echo:
                args:
                    - 'TEST'
                    - 'TEST.*'
    """
    _check_minions_return = {"minions": ["minion1"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "minion1",
                "fun": "test.echo",
                "arg": ["TEST", "any", "TEST ABC"],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "test.echo"
        )


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_args_more_args(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple arg restriction allowed to pass unlisted args.

    'test_user_func':
        minion1:
            - test.echo:
                args:
                    - 'TEST'
                    - 'TEST.*'
    """
    _check_minions_return = {"minions": ["minion1"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "minion1",
                "fun": "test.echo",
                "arg": [
                    "TEST",
                    "any",
                    "TEST ABC",
                    "arg 3",
                    {"kwarg1": "val1", "__kwarg__": True},
                ],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "test.echo"
        )


async def test_args_simple_forbidden(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple arg restriction forbidden.

    'test_user_func':
        minion1:
            - test.echo:
                args:
                    - 'TEST'
                    - 'TEST.*'
    """
    _check_minions_return = {"minions": ["minion1"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        # Wrong last arg
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "minion1",
                "fun": "test.echo",
                "arg": ["TEST", "any", "TESLA"],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Wrong first arg
        master_acl_valid_load["arg"] = ["TES", "any", "TEST1234"]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Missing the last arg
        master_acl_valid_load["arg"] = ["TEST", "any"]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # No args
        master_acl_valid_load["arg"] = []
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_args_kwargs_match(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple kwargs restriction allowed.

    'test_user_func':
      '*':
        - test.echo:
            kwargs:
              text: 'KWMSG:.*'
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "*",
                "fun": "test.echo",
                "arg": [
                    {
                        "text": "KWMSG: a message",
                        "anything": "hello all",
                        "none": "hello none",
                        "__kwarg__": True,
                    }
                ],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            in "test.echo"
        )


async def test_args_kwargs_mismatch(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test simple kwargs restriction allowed.

    'test_user_func':
        '*':
            - test.echo:
                kwargs:
                    text: 'KWMSG:.*'
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {"user": "test_user_func", "tgt": "*", "fun": "test.echo"}
        )
        # Wrong kwarg value
        master_acl_valid_load["arg"] = [
            {
                "text": "KWMSG a message",
                "anything": "hello all",
                "none": "hello none",
                "__kwarg__": True,
            }
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Missing kwarg value
        master_acl_valid_load["arg"] = [
            {"anything": "hello all", "none": "hello none", "__kwarg__": True}
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        master_acl_valid_load["arg"] = [{"__kwarg__": True}]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        master_acl_valid_load["arg"] = [{}]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        master_acl_valid_load["arg"] = []
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Missing kwarg allowing any value
        master_acl_valid_load["arg"] = [
            {"text": "KWMSG: a message", "none": "hello none", "__kwarg__": True}
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        master_acl_valid_load["arg"] = [
            {"text": "KWMSG: a message", "anything": "hello all", "__kwarg__": True}
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_args_mixed_match(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test mixed args and kwargs restriction allowed.

    'test_user_func':
        '*':
            - 'my_mod.*':
                args:
                    - 'a.*'
                    - 'b.*'
                kwargs:
                    'kwa': 'kwa.*'
                    'kwb': 'kwb'
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {
                "user": "test_user_func",
                "tgt": "*",
                "fun": "my_mod.some_func",
                "arg": [
                    "alpha",
                    "beta",
                    "gamma",
                    {
                        "kwa": "kwarg #1",
                        "kwb": "kwb",
                        "one_more": "just one more",
                        "__kwarg__": True,
                    },
                ],
            }
        )
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            master_acl_clear_funcs.event.fire_event.call_args[0][0]["fun"]
            == "my_mod.some_func"
        )


async def test_args_mixed_mismatch(master_acl_clear_funcs, master_acl_valid_load):
    """
    Test mixed args and kwargs restriction forbidden.

    'test_user_func':
        '*':
            - 'my_mod.*':
                args:
                    - 'a.*'
                    - 'b.*'
                kwargs:
                    'kwa': 'kwa.*'
                    'kwb': 'kwb'
    """
    _check_minions_return = {"minions": ["some_minions"], "missing": []}
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value=_check_minions_return),
    ):
        master_acl_valid_load["kwargs"].update({"username": "test_user_func"})
        master_acl_valid_load.update(
            {"user": "test_user_func", "tgt": "*", "fun": "my_mod.some_func"}
        )
        # Wrong arg value
        master_acl_valid_load["arg"] = [
            "alpha",
            "gamma",
            {
                "kwa": "kwarg #1",
                "kwb": "kwb",
                "one_more": "just one more",
                "__kwarg__": True,
            },
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Wrong kwarg value
        master_acl_valid_load["arg"] = [
            "alpha",
            "beta",
            "gamma",
            {
                "kwa": "kkk",
                "kwb": "kwb",
                "one_more": "just one more",
                "__kwarg__": True,
            },
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Missing arg
        master_acl_valid_load["arg"] = [
            "alpha",
            {
                "kwa": "kwarg #1",
                "kwb": "kwb",
                "one_more": "just one more",
                "__kwarg__": True,
            },
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []
        # Missing kwarg
        master_acl_valid_load["arg"] = [
            "alpha",
            "beta",
            "gamma",
            {"kwa": "kwarg #1", "one_more": "just one more", "__kwarg__": True},
        ]
        await master_acl_clear_funcs.publish(master_acl_valid_load)
        assert (
            "error"
            in master_acl_clear_funcs.event.fire_event.mock_calls.pop(-1).args[0]
        )
        assert master_acl_clear_funcs.event.fire_event.mock_calls == []


@pytest.mark.skip_on_windows(reason="PAM eauth not available on Windows")
async def test_acl_simple_allow(auth_acl_clear_funcs, auth_acl_valid_load):
    await auth_acl_clear_funcs.publish(auth_acl_valid_load)
    assert auth_acl_clear_funcs.ckminions.auth_check.call_args[0][0] == [
        {"alpha_minion": ["test.ping"]}
    ]


async def test_acl_simple_deny(auth_acl_clear_funcs, auth_acl_valid_load):
    with patch(
        "salt.auth.LoadAuth.get_auth_list",
        MagicMock(return_value=[{"beta_minion": ["test.ping"]}]),
    ):
        await auth_acl_clear_funcs.publish(auth_acl_valid_load)
        assert auth_acl_clear_funcs.ckminions.auth_check.call_args[0][0] == [
            {"beta_minion": ["test.ping"]}
        ]
