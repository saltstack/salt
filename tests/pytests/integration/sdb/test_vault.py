"""
Integration tests for the vault modules
"""

import json
import logging
import subprocess
import time

import pytest
from pytestshellutils.utils.processes import ProcessResult

import salt.utils.path
from tests.support.helpers import PatchedEnviron
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
]


@pytest.fixture(scope="module")
def patched_environ(vault_port):
    with PatchedEnviron(VAULT_ADDR=f"http://127.0.0.1:{vault_port}"):
        yield


def vault_container_version_id(value):
    return f"vault=={value}"


@pytest.fixture(
    scope="module",
    autouse=True,
    params=["0.9.6", "1.3.1", "latest"],
    ids=vault_container_version_id,
)
def vault_container_version(request, salt_factories, vault_port, patched_environ):
    vault_version = request.param
    vault_binary = salt.utils.path.which("vault")
    config = {
        "backend": {"file": {"path": "/vault/file"}},
        "default_lease_ttl": "168h",
        "max_lease_ttl": "720h",
    }
    factory = salt_factories.get_container(
        "vault",
        f"ghcr.io/saltstack/salt-ci-containers/vault:{vault_version}",
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
                capture_output=True,
                text=True,
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

        proc = subprocess.run(
            [
                vault_binary,
                "policy",
                "write",
                "testpolicy",
                f"{RUNTIME_VARS.FILES}/vault.hcl",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            ret = ProcessResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                cmdline=proc.args,
            )
            log.debug("Failed to assign policy to vault:\n%s", ret)
            pytest.fail("unable to assign policy to vault")
        if vault_version in ("1.3.1", "latest"):
            proc = subprocess.run(
                [vault_binary, "secrets", "enable", "kv-v2"],
                check=False,
                capture_output=True,
                text=True,
            )
            ret = ProcessResult(
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                cmdline=proc.args,
            )
            if proc.returncode != 0:
                log.debug("Failed to enable kv-v2:\n%s", ret)
                pytest.fail("Could not enable kv-v2")

            if "path is already in use at kv-v2/" in proc.stdout:
                pass
            elif "Success" in proc.stdout:
                pass
            else:
                log.debug("Failed to enable kv-v2:\n%s", ret)
                pytest.fail(f"Could not enable kv-v2 {proc.stdout}")
            if vault_version == "latest":
                proc = subprocess.run(
                    [
                        vault_binary,
                        "secrets",
                        "enable",
                        "-version=2",
                        "-path=salt/",
                        "kv",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                ret = ProcessResult(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    cmdline=proc.args,
                )
                if proc.returncode != 0:
                    log.debug("Failed to enable kv-v2:\n%s", ret)
                    pytest.fail("Could not enable kv-v2")

                if "path is already in use at kv-v2/" in proc.stdout:
                    pass
                elif "Success" in proc.stdout:
                    proc = subprocess.run(
                        [
                            vault_binary,
                            "kv",
                            "put",
                            "salt/user1",
                            "password=p4ssw0rd",
                            "desc=test user",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    ret = ProcessResult(
                        returncode=proc.returncode,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        cmdline=proc.args,
                    )
                    if proc.returncode != 0:
                        log.debug("Failed to enable kv-v2:\n%s", ret)
                        pytest.fail("Could not enable kv-v2")
                    if "path is already in use at kv-v2/" in proc.stdout:
                        pass
                    elif "created_time" in proc.stdout:
                        proc = subprocess.run(
                            [
                                vault_binary,
                                "kv",
                                "put",
                                "salt/user/user1",
                                "password=p4ssw0rd",
                                "desc=test user",
                            ],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        ret = ProcessResult(
                            returncode=proc.returncode,
                            stdout=proc.stdout,
                            stderr=proc.stderr,
                            cmdline=proc.args,
                        )
                        if proc.returncode != 0:
                            log.debug("Failed to enable kv-v2:\n%s", ret)
                            pytest.fail("Could not enable kv-v2")

                        if "path is already in use at kv-v2/" in proc.stdout:
                            pass
                        elif "created_time" in proc.stdout:
                            proc = subprocess.run(
                                [vault_binary, "kv", "get", "salt/user1"],
                                check=False,
                                capture_output=True,
                                text=True,
                            )
                            ret = ProcessResult(
                                returncode=proc.returncode,
                                stdout=proc.stdout,
                                stderr=proc.stderr,
                                cmdline=proc.args,
                            )

                else:
                    log.debug("Failed to enable kv-v2:\n%s", ret)
                    pytest.fail(f"Could not enable kv-v2 {proc.stdout}")
        yield vault_version


def test_sdb(salt_call_cli):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run("sdb.get", uri="sdb://sdbvault/secret/test/test_sdb/foo")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"


def test_sdb_runner(salt_run_cli):
    ret = salt_run_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_run_cli.run(
        "sdb.get", uri="sdb://sdbvault/secret/test/test_sdb_runner/foo"
    )
    assert ret.returncode == 0
    assert ret.stdout
    assert ret.stdout == "bar"


def test_config(salt_call_cli, pillar_tree):
    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/secret/test/test_pillar_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run("config.get", "test_vault_pillar_sdb")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "bar"


def test_sdb_kv2_kvv2_path_local(salt_call_cli, vault_container_version):
    if vault_container_version not in ["1.3.1", "latest"]:
        pytest.skip(f"Test not applicable to vault {vault_container_version}")

    ret = salt_call_cli.run(
        "sdb.set", uri="sdb://sdbvault/kv-v2/test/test_sdb/foo", value="bar"
    )
    assert ret.returncode == 0
    assert ret.data is True
    ret = salt_call_cli.run(
        "--local", "sdb.get", "sdb://sdbvault/kv-v2/test/test_sdb/foo"
    )
    assert ret.data
    assert ret.data == "bar"


def test_sdb_kv_dual_item(salt_call_cli, vault_container_version):
    if vault_container_version not in ["latest"]:
        pytest.skip(f"Test not applicable to vault {vault_container_version}")
    ret = salt_call_cli.run("--local", "sdb.get", "sdb://sdbvault/salt/data/user1")
    assert ret.data
    assert ret.data == {"desc": "test user", "password": "p4ssw0rd"}
