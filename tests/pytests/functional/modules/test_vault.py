import logging

import pytest

# pylint: disable=unused-import
from tests.support.pytest.vault import (
    vault_container_version,
    vault_delete_policy,
    vault_delete_secret,
    vault_environ,
    vault_list_policies,
    vault_list_secrets,
    vault_read_policy,
    vault_write_policy,
)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
]

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def minion_config_overrides(vault_port):
    return {
        "vault": {
            "auth": {
                "method": "token",
                "token": "testsecret",
            },
            "server": {
                "url": f"http://127.0.0.1:{vault_port}",
            },
        }
    }


@pytest.fixture(scope="module")
def sys_mod(modules):
    return modules.sys


@pytest.fixture
def vault(loaders, modules, vault_container_version):
    try:
        yield modules.vault
    finally:
        # We're explicitly using the vault CLI and not the salt vault module
        secret_path = "secret/my"
        for secret in vault_list_secrets(secret_path):
            vault_delete_secret(f"{secret_path}/{secret}", metadata=True)
        policies = vault_list_policies()
        for policy in ["functional_test_policy", "policy_write_test"]:
            if policy in policies:
                vault_delete_policy(policy)


@pytest.mark.windows_whitelisted
def test_vault_read_secret_issue_61084(sys_mod):
    """
    Test issue 61084. `sys.argspec` should return valid data and not throw a
    TypeError due to pickling
    This should probably be a pre-commit check or something
    """
    result = sys_mod.argspec("vault.read_secret")
    assert isinstance(result, dict)
    assert isinstance(result.get("vault.read_secret"), dict)


@pytest.mark.windows_whitelisted
def test_vault_list_secrets_issue_61084(sys_mod):
    """
    Test issue 61084. `sys.argspec` should return valid data and not throw a
    TypeError due to pickling
    This should probably be a pre-commit check or something
    """
    result = sys_mod.argspec("vault.list_secrets")
    assert isinstance(result, dict)
    assert isinstance(result.get("vault.list_secrets"), dict)


def test_write_read_secret(vault, vault_container_version):
    ret = vault.write_secret(path="secret/my/secret", user="foo", password="bar")
    if vault_container_version == "0.9.6":
        assert ret is True
        ret = vault.read_secret(path="secret/my/secret")
        assert ret == {
            "password": "bar",
            "user": "foo",
        }
        ret = vault.read_secret(path="secret/my/secret", key="user")
        assert ret == "foo"
    else:
        # write_secret output:
        # {'created_time': '2020-01-12T23:09:34.571294241Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}
        assert ret
        expected_write = {"destroyed": False, "deletion_time": ""}
        for key in list(ret):
            if key not in expected_write:
                ret.pop(key)
        assert ret == expected_write

        ret = vault.read_secret("secret/my/secret", metadata=True)
        # read_secret output:
        # {'data': {'password': 'bar', 'user': 'foo'},
        # 'metadata': {'created_time': '2020-01-12T23:07:18.829326918Z', 'destroyed': False,
        # 'version': 1, 'deletion_time': ''}}
        assert ret
        assert "data" in ret
        expected_read = {"password": "bar", "user": "foo"}
        assert "metadata" in ret
        assert ret["data"] == expected_read

        ret = vault.read_secret("secret/my/secret")
        for key in list(ret):
            if key not in expected_read:
                ret.pop(key)
        assert ret == expected_read

        ret = vault.read_secret("secret/my/secret", key="user")
        assert ret == "foo"


def test_write_raw_read_secret(vault, vault_container_version):
    ret = vault.write_raw(
        "secret/my/secret2", raw={"user2": "foo2", "password2": "bar2"}
    )
    if vault_container_version == "0.9.6":
        assert ret is True
        ret = vault.read_secret("secret/my/secret2")
        assert ret == {
            "password2": "bar2",
            "user2": "foo2",
        }
    else:
        assert ret
        expected_write = {"destroyed": False, "deletion_time": ""}
        for key in list(ret):
            if key not in expected_write:
                ret.pop(key)
        assert ret == expected_write

        expected_read = {"password2": "bar2", "user2": "foo2"}
        ret = vault.read_secret("secret/my/secret2", metadata=True)
        assert ret
        assert "metadata" in ret
        assert "data" in ret
        assert ret["data"] == expected_read

        ret = vault.read_secret("secret/my/secret2")
        for key in list(ret):
            if key not in expected_read:
                ret.pop(key)
        assert ret == expected_read


@pytest.fixture
def existing_secret(vault, vault_container_version):
    ret = vault.write_secret("secret/my/secret", user="foo", password="bar")
    if vault_container_version == "0.9.6":
        assert ret is True
    else:
        expected_write = {"destroyed": False, "deletion_time": ""}
        for key in list(ret):
            if key not in expected_write:
                ret.pop(key)
        assert ret == expected_write


@pytest.fixture
def existing_secret_version(existing_secret, vault, vault_container_version):
    ret = vault.write_secret("secret/my/secret", user="foo", password="hunter1")
    assert ret
    assert ret["version"] == 2
    ret = vault.read_secret("secret/my/secret")
    assert ret
    assert ret["password"] == "hunter1"


@pytest.mark.usefixtures("existing_secret")
def test_delete_secret(vault):
    ret = vault.delete_secret("secret/my/secret")
    assert ret is True


@pytest.mark.usefixtures("existing_secret_version")
@pytest.mark.parametrize("vault_container_version", ["1.3.1", "latest"], indirect=True)
def test_delete_secret_versions(vault, vault_container_version):
    ret = vault.delete_secret("secret/my/secret", 1)
    assert ret is True
    ret = vault.read_secret("secret/my/secret")
    assert ret
    assert ret["password"] == "hunter1"
    ret = vault.delete_secret("secret/my/secret", 2)
    assert ret is True
    ret = vault.read_secret("secret/my/secret", default="__was_deleted__")
    assert ret == "__was_deleted__"


@pytest.mark.usefixtures("existing_secret")
def test_list_secrets(vault):
    ret = vault.list_secrets("secret/my/")
    assert ret
    assert "keys" in ret
    assert ret["keys"] == ["secret"]


@pytest.mark.usefixtures("existing_secret")
@pytest.mark.parametrize("vault_container_version", ["1.3.1", "latest"], indirect=True)
def test_destroy_secret_kv2(vault, vault_container_version):
    ret = vault.destroy_secret("secret/my/secret", "1")
    assert ret is True


@pytest.mark.usefixtures("existing_secret")
@pytest.mark.parametrize("vault_container_version", ["latest"], indirect=True)
def test_patch_secret(vault, vault_container_version):
    ret = vault.patch_secret("secret/my/secret", password="baz")
    assert ret
    expected_write = {"destroyed": False, "deletion_time": ""}
    for key in list(ret):
        if key not in expected_write:
            ret.pop(key)
    assert ret == expected_write
    ret = vault.read_secret("secret/my/secret")
    assert ret == {"user": "foo", "password": "baz"}


@pytest.fixture
def policy_rules():
    return """\
path "secret/some/thing" {
    capabilities = ["read"]
}
    """


@pytest.fixture
def existing_policy(policy_rules, vault_container_version):
    vault_write_policy("functional_test_policy", policy_rules)
    try:
        yield
    finally:
        vault_delete_policy("functional_test_policy")


@pytest.mark.usefixtures("existing_policy")
def test_policy_fetch(vault, policy_rules):
    ret = vault.policy_fetch("functional_test_policy")
    assert ret == policy_rules
    ret = vault.policy_fetch("__does_not_exist__")
    assert ret is None


def test_policy_write(vault, policy_rules):
    ret = vault.policy_write("policy_write_test", policy_rules)
    assert ret is True
    assert vault_read_policy("policy_write_test") == policy_rules


@pytest.mark.usefixtures("existing_policy")
def test_policy_delete(vault):
    ret = vault.policy_delete("functional_test_policy")
    assert ret is True
    assert "functional_test_policy" not in vault_list_policies()


@pytest.mark.usefixtures("existing_policy")
def test_policies_list(vault):
    ret = vault.policies_list()
    assert "functional_test_policy" in ret
