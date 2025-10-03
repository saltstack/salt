import logging

import pytest

import salt.exceptions
import salt.modules.vault as vault
import salt.utils.vault as vaultutil
from tests.support.mock import ANY, patch


@pytest.fixture
def configure_loader_modules():
    return {
        vault: {
            "__grains__": {"id": "test-minion"},
        }
    }


@pytest.fixture
def data():
    return {"foo": "bar"}


@pytest.fixture
def policy_response():
    return {
        "name": "test-policy",
        "rules": 'path "secret/*"\\n{\\n  capabilities = ["read"]\\n}',
    }


@pytest.fixture
def policies_list_response():
    return {
        "policies": ["default", "root", "test-policy"],
    }


@pytest.fixture
def data_list():
    return ["foo"]


@pytest.fixture
def read_kv(data):
    with patch("salt.utils.vault.read_kv", autospec=True) as read:
        read.return_value = data
        yield read


@pytest.fixture
def list_kv(data_list):
    with patch("salt.utils.vault.list_kv", autospec=True) as list:
        list.return_value = data_list
        yield list


@pytest.fixture
def read_kv_not_found(read_kv):
    read_kv.side_effect = vaultutil.VaultNotFoundError
    yield read_kv


@pytest.fixture
def list_kv_not_found(list_kv):
    list_kv.side_effect = vaultutil.VaultNotFoundError
    yield list_kv


@pytest.fixture
def write_kv():
    with patch("salt.utils.vault.write_kv", autospec=True) as write:
        yield write


@pytest.fixture
def write_kv_err(write_kv):
    write_kv.side_effect = vaultutil.VaultPermissionDeniedError("damn")
    yield write_kv


@pytest.fixture
def patch_kv():
    with patch("salt.utils.vault.patch_kv", autospec=True) as patch_kv:
        yield patch_kv


@pytest.fixture
def patch_kv_err(patch_kv):
    patch_kv.side_effect = vaultutil.VaultPermissionDeniedError("damn")
    yield patch_kv


@pytest.fixture
def delete_kv():
    with patch("salt.utils.vault.delete_kv", autospec=True) as delete_kv:
        yield delete_kv


@pytest.fixture
def delete_kv_err(delete_kv):
    delete_kv.side_effect = vaultutil.VaultPermissionDeniedError("damn")
    yield delete_kv


@pytest.fixture
def destroy_kv():
    with patch("salt.utils.vault.destroy_kv", autospec=True) as destroy_kv:
        yield destroy_kv


@pytest.fixture
def destroy_kv_err(destroy_kv):
    destroy_kv.side_effect = vaultutil.VaultPermissionDeniedError("damn")
    yield destroy_kv


@pytest.fixture
def query():
    with patch("salt.utils.vault.query", autospec=True) as query:
        yield query


@pytest.mark.parametrize("key,expected", [(None, {"foo": "bar"}), ("foo", "bar")])
def test_read_secret(read_kv, key, expected):
    """
    Ensure read_secret works as expected without and with specified key.
    KV v1/2 is handled in the utils module.
    """
    res = vault.read_secret("some/path", key=key)
    assert res == expected


@pytest.mark.usefixtures("read_kv_not_found", "list_kv_not_found")
@pytest.mark.parametrize("func", ["read_secret", "list_secrets"])
def test_read_list_secret_with_default(func):
    """
    Ensure read_secret and list_secrets with defaults set return those
    if the path was not found.
    """
    tgt = getattr(vault, func)
    res = tgt("some/path", default=["f"])
    assert res == ["f"]


@pytest.mark.usefixtures("read_kv_not_found", "list_kv_not_found")
@pytest.mark.parametrize("func", ["read_secret", "list_secrets"])
def test_read_list_secret_without_default(func):
    """
    Ensure read_secret and list_secrets without defaults set raise
    a CommandExecutionError when the path is not found.
    """
    tgt = getattr(vault, func)
    with pytest.raises(
        salt.exceptions.CommandExecutionError, match=".*VaultNotFoundError.*"
    ):
        tgt("some/path")


@pytest.mark.usefixtures("list_kv")
@pytest.mark.parametrize(
    "keys_only,expected",
    [
        (False, {"keys": ["foo"]}),
        (True, ["foo"]),
    ],
)
def test_list_secrets(keys_only, expected):
    """
    Ensure list_secrets works as expected. keys_only=False is default to
    stay backwards-compatible. There should not be a reason to have the
    function return a dict with a single predictable key otherwise.
    """
    res = vault.list_secrets("some/path", keys_only=keys_only)
    assert res == expected


def test_write_secret(data, write_kv):
    """
    Ensure write_secret parses kwargs as expected
    """
    path = "secret/some/path"
    res = vault.write_secret(path, **data)
    assert res
    write_kv.assert_called_once_with(path, data, opts=ANY, context=ANY)


@pytest.mark.usefixtures("write_kv_err")
def test_write_secret_err(data, caplog):
    """
    Ensure write_secret handles exceptions as expected
    """
    with caplog.at_level(logging.ERROR):
        res = vault.write_secret("secret/some/path", **data)
        assert not res
        assert (
            "Failed to write secret! VaultPermissionDeniedError: damn"
            in caplog.messages
        )


def test_write_raw(data, write_kv):
    """
    Ensure write_secret works as expected
    """
    path = "secret/some/path"
    res = vault.write_raw(path, data)
    assert res
    write_kv.assert_called_once_with(path, data, opts=ANY, context=ANY)


@pytest.mark.usefixtures("write_kv_err")
def test_write_raw_err(data, caplog):
    """
    Ensure write_raw handles exceptions as expected
    """
    with caplog.at_level(logging.ERROR):
        res = vault.write_raw("secret/some/path", data)
        assert not res
        assert (
            "Failed to write secret! VaultPermissionDeniedError: damn"
            in caplog.messages
        )


def test_patch_secret(data, patch_kv):
    """
    Ensure patch_secret parses kwargs as expected
    """
    path = "secret/some/path"
    res = vault.patch_secret(path, **data)
    assert res
    patch_kv.assert_called_once_with(path, data, opts=ANY, context=ANY)


@pytest.mark.usefixtures("patch_kv_err")
def test_patch_secret_err(data, caplog):
    """
    Ensure patch_secret handles exceptions as expected
    """
    with caplog.at_level(logging.ERROR):
        res = vault.patch_secret("secret/some/path", **data)
        assert not res
        assert (
            "Failed to patch secret! VaultPermissionDeniedError: damn"
            in caplog.messages
        )


@pytest.mark.parametrize("args", [[], [1, 2]])
def test_delete_secret(delete_kv, args):
    """
    Ensure delete_secret works as expected
    """
    path = "secret/some/path"
    res = vault.delete_secret(path, *args)
    assert res
    delete_kv.assert_called_once_with(
        path, opts=ANY, context=ANY, versions=args or None
    )


@pytest.mark.usefixtures("delete_kv_err")
@pytest.mark.parametrize("args", [[], [1, 2]])
def test_delete_secret_err(args, caplog):
    """
    Ensure delete_secret handles exceptions as expected
    """
    with caplog.at_level(logging.ERROR):
        res = vault.delete_secret("secret/some/path", *args)
        assert not res
        assert (
            "Failed to delete secret! VaultPermissionDeniedError: damn"
            in caplog.messages
        )


@pytest.mark.parametrize("args", [[1], [1, 2]])
def test_destroy_secret(destroy_kv, args):
    """
    Ensure destroy_secret works as expected
    """
    path = "secret/some/path"
    res = vault.destroy_secret(path, *args)
    assert res
    destroy_kv.assert_called_once_with(path, args, opts=ANY, context=ANY)


@pytest.mark.usefixtures("destroy_kv")
def test_destroy_secret_requires_version():
    """
    Ensure destroy_secret requires at least one version
    """
    with pytest.raises(
        salt.exceptions.SaltInvocationError, match=".*at least one version.*"
    ):
        vault.destroy_secret("secret/some/path")


@pytest.mark.usefixtures("destroy_kv_err")
@pytest.mark.parametrize("args", [[1], [1, 2]])
def test_destroy_secret_err(caplog, args):
    """
    Ensure destroy_secret handles exceptions as expected
    """
    with caplog.at_level(logging.ERROR):
        res = vault.destroy_secret("secret/some/path", *args)
        assert not res
        assert (
            "Failed to destroy secret! VaultPermissionDeniedError: damn"
            in caplog.messages
        )


def test_clear_token_cache():
    """
    Ensure clear_token_cache wraps the utility function properly
    """
    with patch("salt.utils.vault.clear_cache") as cache:
        vault.clear_token_cache()
        cache.assert_called_once_with(ANY, ANY, connection=True, session=False)


def test_policy_fetch(query, policy_response):
    """
    Ensure policy_fetch returns rules only and calls the API as expected
    """
    query.return_value = policy_response
    res = vault.policy_fetch("test-policy")
    assert res == policy_response["rules"]
    query.assert_called_once_with(
        "GET", "sys/policy/test-policy", opts=ANY, context=ANY
    )


def test_policy_fetch_not_found(query):
    """
    Ensure policy_fetch returns None when the policy was not found
    """
    query.side_effect = vaultutil.VaultNotFoundError
    res = vault.policy_fetch("test-policy")
    assert res is None


@pytest.mark.parametrize(
    "func,args",
    [
        ("policy_fetch", []),
        ("policy_write", ["rule"]),
        ("policy_delete", []),
        ("policies_list", None),
    ],
)
def test_policy_functions_raise_errors(query, func, args):
    """
    Ensure policy functions raise CommandExecutionErrors
    """
    query.side_effect = vaultutil.VaultPermissionDeniedError
    func = getattr(vault, func)
    with pytest.raises(
        salt.exceptions.CommandExecutionError, match=".*VaultPermissionDeniedError.*"
    ):
        if args is None:
            func()
        else:
            func("test-policy", *args)


def test_policy_write(query, policy_response):
    """
    Ensure policy_write calls the API as expected
    """
    query.return_value = True
    res = vault.policy_write("test-policy", policy_response["rules"])
    assert res
    query.assert_called_once_with(
        "POST",
        "sys/policy/test-policy",
        opts=ANY,
        context=ANY,
        payload={"policy": policy_response["rules"]},
    )


def test_policy_delete(query):
    """
    Ensure policy_delete calls the API as expected
    """
    query.return_value = True
    res = vault.policy_delete("test-policy")
    assert res
    query.assert_called_once_with(
        "DELETE", "sys/policy/test-policy", opts=ANY, context=ANY
    )


def test_policy_delete_handles_not_found(query):
    """
    Ensure policy_delete returns False instead of raising CommandExecutionError
    when a policy was absent already.
    """
    query.side_effect = vaultutil.VaultNotFoundError
    res = vault.policy_delete("test-policy")
    assert not res


def test_policies_list(query, policies_list_response):
    """
    Ensure policies_list returns policy list only and calls the API as expected
    """
    query.return_value = policies_list_response
    res = vault.policies_list()
    assert res == policies_list_response["policies"]
    query.assert_called_once_with("GET", "sys/policy", opts=ANY, context=ANY)


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("payload", [None, {"data": {"foo": "bar"}}])
def test_query(query, method, payload):
    """
    Ensure query wraps the utility function properly
    """
    query.return_value = True
    endpoint = "test/endpoint"
    res = vault.query(method, endpoint, payload=payload)
    assert res
    query.assert_called_once_with(
        method, endpoint, opts=ANY, context=ANY, payload=payload
    )


def test_query_raises_errors(query):
    """
    Ensure query raises CommandExecutionErrors
    """
    query.side_effect = vaultutil.VaultPermissionDeniedError
    with pytest.raises(
        salt.exceptions.CommandExecutionError, match=".*VaultPermissionDeniedError.*"
    ):
        vault.query("GET", "test/endpoint")
