import json
import logging
import subprocess
import time

import pytest
from pytestshellutils.utils.processes import ProcessResult

import salt.utils.files
import salt.utils.path
from tests.support.helpers import PatchedEnviron
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def vault_write_policy(name, rules):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "policy", "write", name, "-"],
        check=False,
        input=rules,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug("Failed to write policy `%s`:\n%s", name, ret)
        pytest.fail(f"Unable to write policy `{name}`")


def vault_write_policy_file(policy, filename=None):
    vault_binary = salt.utils.path.which("vault")
    if filename is None:
        filename = policy
    proc = subprocess.run(
        [
            vault_binary,
            "policy",
            "write",
            policy,
            f"{RUNTIME_VARS.FILES}/vault/policies/{filename}.hcl",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug("Failed to write policy `%s`:\n%s", policy, ret)
        pytest.fail(f"Unable to write policy `{policy}`")


def vault_read_policy(policy):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [
            vault_binary,
            "policy",
            "read",
            "-format=json",
            policy,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        if "No policy named" in proc.stderr:
            return None
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug("Failed to read policy `%s`:\n%s", policy, ret)
        pytest.fail(f"Unable to read policy `{policy}`")
    res = json.loads(proc.stdout)
    return res["policy"]


def vault_list_policies():
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [
            vault_binary,
            "policy",
            "list",
            "-format=json",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug("Failed to list policies:\n%s", ret)
        pytest.fail("Unable to list policies")
    return json.loads(proc.stdout)


def vault_delete_policy(policy):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [
            vault_binary,
            "policy",
            "delete",
            policy,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0 or vault_read_policy(policy) is not None:
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug("Failed to delete policy `%s`:\n%s", policy, ret)
        pytest.fail(f"Unable to delete policy `{policy}`")


def vault_enable_secret_engine(name, options=None, **kwargs):
    vault_binary = salt.utils.path.which("vault")
    if options is None:
        options = []
    cmd = [vault_binary, "secrets", "enable"] + options + [name]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        log.debug("Failed to enable secret engine `%s`:\n%s", name, ret)
        pytest.fail(f"Could not enable secret engine `{name}`")

    if "path is already in use at" in proc.stdout:
        return False
    if "Success" in proc.stdout:
        return True

    log.debug("Failed to enable secret engine `%s`:\n%s", name, ret)
    pytest.fail(f"Could not enable secret engine `{name}`: {proc.stdout}")


def vault_disable_secret_engine(name):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "secrets", "disable", name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        log.debug("Failed to disable secret engine `%s`:\n%s", name, ret)
        pytest.fail(f"Could not disable secret engine `{name}`")

    if "Success" in proc.stdout:
        return True

    log.debug("Failed to disable secret engine `%s`:\n%s", name, ret)
    pytest.fail(f"Could not disable secret engine `{name}`: {proc.stdout}")


def vault_enable_auth_method(name, options=None, **kwargs):
    vault_binary = salt.utils.path.which("vault")
    if options is None:
        options = []
    cmd = (
        [vault_binary, "auth", "enable"]
        + options
        + [name]
        + [f"{k}={v}" for k, v in kwargs.items()]
    )
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        log.debug("Failed to enable auth method `%s`:\n%s", name, ret)
        pytest.fail(f"Could not enable auth method `{name}`")

    if "path is already in use at" in proc.stdout:
        return False
    if "Success" in proc.stdout:
        return True

    log.debug("Failed to enable auth method `%s`:\n%s", name, ret)
    pytest.fail(f"Could not enable auth method `{name}`: {proc.stdout}")


def vault_disable_auth_method(name):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "auth", "disable", name],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        log.debug("Failed to disable auth method `%s`:\n%s", name, ret)
        pytest.fail(f"Could not disable auth method `{name}`")

    if "Success" in proc.stdout:
        return True

    log.debug("Failed to disable auth method `%s`:\n%s", name, ret)
    pytest.fail(f"Could not disable auth method `{name}`: {proc.stdout}")


def vault_write_secret(path, **kwargs):
    vault_binary = salt.utils.path.which("vault")
    cmd = [vault_binary, "kv", "put", path] + [f"{k}={v}" for k, v in kwargs.items()]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0 or vault_read_secret(path) != kwargs:
        log.debug("Failed to write secret at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to write secret at `{path}`")
    return True


def vault_write_secret_file(path, data_name):
    vault_binary = salt.utils.path.which("vault")
    data_path = f"{RUNTIME_VARS.FILES}/vault/data/{data_name}.json"
    with salt.utils.files.fopen(data_path) as f:
        data = json.load(f)
    cmd = [vault_binary, "kv", "put", path, f"@{data_path}"]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0 or vault_read_secret(path) != data:
        log.debug("Failed to write secret at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to write secret at `{path}`")
    return True


def vault_read_secret(path):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "kv", "get", "-format=json", path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        if "No value found at" in proc.stderr:
            return None
        log.debug("Failed to read secret at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to read secret at `{path}`")
    res = json.loads(proc.stdout)
    if "data" in res["data"]:
        return res["data"]["data"]
    return res["data"]


def vault_list_secrets(path):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "kv", "list", "-format=json", path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0:
        if proc.returncode == 2:
            return []
        log.debug("Failed to list secrets at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to list secrets at `{path}`")
    return json.loads(proc.stdout)


def vault_delete_secret(path, metadata=False):
    vault_binary = salt.utils.path.which("vault")
    proc = subprocess.run(
        [vault_binary, "kv", "delete", path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if proc.returncode != 0 or vault_read_secret(path) is not None:
        log.debug("Failed to delete secret at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to delete secret at `{path}`")

    if not metadata:
        return True

    proc = subprocess.run(
        [vault_binary, "kv", "metadata", "delete", path],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    ret = ProcessResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmdline=proc.args,
    )
    if (
        proc.returncode != 0
        and "Metadata not supported on KV Version 1" not in proc.stderr
    ):
        log.debug("Failed to delete secret metadata at `%s`:\n%s", path, ret)
        pytest.fail(f"Failed to delete secret metadata at `{path}`")
    return True


@pytest.fixture(scope="session")
def vault_environ(vault_port):
    with PatchedEnviron(VAULT_ADDR="http://127.0.0.1:{}".format(vault_port)):
        yield


def vault_container_version_id(value):
    return "vault=={}".format(value)


@pytest.fixture(
    scope="session",
    params=["0.9.6", "1.3.1", "latest"],
    ids=vault_container_version_id,
)
def vault_container_version(request, salt_factories, vault_port, vault_environ):
    vault_version = request.param
    vault_binary = salt.utils.path.which("vault")
    config = {
        "backend": {"file": {"path": "/vault/file"}},
        "default_lease_ttl": "168h",
        "max_lease_ttl": "720h",
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
            proc = subprocess.run(
                [vault_binary, "login", "token=testsecret"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if proc.returncode == 0:
                break
            ret = ProcessResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                cmdline=proc.args,
            )
            log.debug("Failed to authenticate against vault:\n%s", ret)
            time.sleep(4)
        else:
            pytest.fail("Failed to login to vault")

        vault_write_policy_file("salt_master")

        if "latest" == vault_version:
            vault_write_policy_file("salt_minion")
        else:
            vault_write_policy_file("salt_minion", "salt_minion_old")

        if vault_version in ("1.3.1", "latest"):
            vault_enable_secret_engine("kv-v2")
            if vault_version == "latest":
                vault_enable_secret_engine("kv", ["-version=2", "-path=salt"])

        yield vault_version
