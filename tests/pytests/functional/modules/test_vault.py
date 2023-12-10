import json
import logging
import time

import pytest

import salt.utils.path
from tests.support.runtests import RUNTIME_VARS

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
]

VAULT_BINARY = salt.utils.path.which("vault")

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def minion_config_overrides(vault_port):
    return {
        "vault": {
            "url": "http://127.0.0.1:{}".format(vault_port),
            "auth": {
                "method": "token",
                "token": "testsecret",
                "uses": 0,
                "policies": [
                    "testpolicy",
                ],
            },
        }
    }


def vault_container_version_id(value):
    return "vault=={}".format(value)


@pytest.fixture(
    scope="module",
    params=["0.9.6", "1.3.1", "latest"],
    ids=vault_container_version_id,
)
def vault_container_version(request, salt_factories, vault_port, shell):
    vault_version = request.param
    config = {
        "backend": {"file": {"path": "/vault/file"}},
        "default_lease_ttl": "168h",
        "max_lease_ttl": "720h",
        "disable_mlock": False,
    }

    factory = salt_factories.get_container(
        "vault",
        "ghcr.io/saltstack/salt-ci-containers/vault:{}".format(vault_version),
        check_ports=[vault_port],
        container_run_kwargs={
            "ports": {"8200/tcp": vault_port},
            "environment": {
                "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                "VAULT_LOCAL_CONFIG": json.dumps(config),
            },
            "cap_add": "IPC_LOCK",
        },
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    with factory.started() as factory:
        attempts = 0
        while attempts < 3:
            attempts += 1
            time.sleep(1)
            ret = shell.run(
                VAULT_BINARY,
                "login",
                "token=testsecret",
                env={"VAULT_ADDR": "http://127.0.0.1:{}".format(vault_port)},
            )
            if ret.returncode == 0:
                break
            log.debug("Failed to authenticate against vault:\n%s", ret)
            time.sleep(4)
        else:
            pytest.fail("Failed to login to vault")

        ret = shell.run(
            VAULT_BINARY,
            "policy",
            "write",
            "testpolicy",
            "{}/vault.hcl".format(RUNTIME_VARS.FILES),
            env={"VAULT_ADDR": "http://127.0.0.1:{}".format(vault_port)},
        )
        if ret.returncode != 0:
            log.debug("Failed to assign policy to vault:\n%s", ret)
            pytest.fail("unable to assign policy to vault")
        yield vault_version


@pytest.fixture(scope="module")
def sys_mod(modules):
    return modules.sys


@pytest.fixture
def vault(loaders, modules, vault_container_version, shell, vault_port):
    try:
        yield modules.vault
    finally:
        # We're explicitly using the vault CLI and not the salt vault module
        secret_path = "secret/my"
        ret = shell.run(
            VAULT_BINARY,
            "kv",
            "list",
            "--format=json",
            secret_path,
            env={"VAULT_ADDR": "http://127.0.0.1:{}".format(vault_port)},
        )
        if ret.returncode == 0:
            for secret in ret.data:
                secret_path = "secret/my/{}".format(secret)
                ret = shell.run(
                    VAULT_BINARY,
                    "kv",
                    "delete",
                    secret_path,
                    env={"VAULT_ADDR": "http://127.0.0.1:{}".format(vault_port)},
                )
                ret = shell.run(
                    VAULT_BINARY,
                    "kv",
                    "metadata",
                    "delete",
                    secret_path,
                    env={"VAULT_ADDR": "http://127.0.0.1:{}".format(vault_port)},
                )


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


@pytest.mark.usefixtures("existing_secret")
def test_delete_secret(vault):
    ret = vault.delete_secret("secret/my/secret")
    assert ret is True


@pytest.mark.usefixtures("existing_secret")
def test_list_secrets(vault):
    ret = vault.list_secrets("secret/my/")
    assert ret
    assert "keys" in ret
    assert ret["keys"] == ["secret"]


@pytest.mark.usefixtures("existing_secret")
def test_destroy_secret_kv2(vault, vault_container_version):
    if vault_container_version == "0.9.6":
        pytest.skip("Test not applicable to vault=={}".format(vault_container_version))
    ret = vault.destroy_secret("secret/my/secret", "1")
    assert ret is True
