"""
Integration tests for the vault modules
"""
import json
import logging
import os
import subprocess
import time

import pytest
import salt.utils.path
from pytestshellutils.utils.processes import ProcessResult
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_if_binaries_missing("dockerd", "vault", "getent"),
]


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir, salt_minion):
    top_file = """
    base:
      '{}':
        - sdb
    """.format(
        salt_minion.id
    )
    sdb_pillar_file = """
    test_vault_pillar_sdb: sdb://sdbvault/secret/test/test_pillar_sdb/foo
    test_etcd_pillar_sdb: sdb://sdbetcd/secret/test/test_pillar_sdb/foo
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    sdb_tempfile = pytest.helpers.temp_file(
        "sdb.sls", sdb_pillar_file, base_env_pillar_tree_root_dir
    )

    with top_tempfile, sdb_tempfile:
        yield


def vault_container_version_id(value):
    return "vault=={}".format(value)


@pytest.fixture(
    scope="module",
    autouse=True,
    params=["0.9.6", "1.3.1", "latest"],
    ids=vault_container_version_id,
)
def vault_container_version(request, salt_call_cli, vault_port):
    vault_version = request.param
    container_started = False
    try:
        vault_binary = salt.utils.path.which("vault")
        config = {
            "backend": {"file": {"path": "/vault/file"}},
            "default_lease_ttl": "168h",
            "max_lease_ttl": "720h",
        }
        ret = salt_call_cli.run(
            "state.single", "docker_image.present", name="vault", tag=vault_version
        )
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True

        container_started = True
        attempts = 0
        env = os.environ.copy()
        env["VAULT_ADDR"] = "http://127.0.0.1:{}".format(vault_port)
        while attempts < 3:
            attempts += 1
            ret = salt_call_cli.run(
                "state.single",
                "docker_container.running",
                name="vault",
                image="vault:{}".format(vault_version),
                port_bindings="{}:8200".format(vault_port),
                environment={
                    "VAULT_DEV_ROOT_TOKEN_ID": "testsecret",
                    "VAULT_LOCAL_CONFIG": json.dumps(config),
                },
                cap_add="IPC_LOCK",
            )
            assert ret.returncode == 0
            assert ret.data
            state_run = next(iter(ret.data.values()))
            assert state_run["result"] is True

            time.sleep(1)
            proc = subprocess.run(
                [vault_binary, "login", "token=testsecret"],
                env=env,
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

        proc = subprocess.run(
            [
                vault_binary,
                "policy",
                "write",
                "testpolicy",
                "{}/vault.hcl".format(RUNTIME_VARS.FILES),
            ],
            env=env,
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
            log.debug("Failed to assign policy to vault:\n%s", ret)
            pytest.fail("unable to assign policy to vault")
        if vault_version in ["1.3.1", "latest"]:
            proc = subprocess.run(
                [vault_binary, "secrets", "enable", "kv-v2"],
                env=env,
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
                log.debug("Failed to enable kv-v2:\n%s", ret)
                pytest.fail("Could not enable kv-v2")

            if "path is already in use at kv-v2/" in proc.stdout:
                pass
            elif "Success" in proc.stdout:
                pass
            else:
                log.debug("Failed to enable kv-v2:\n%s", ret)
                pytest.fail("Could not enable kv-v2 {}".format(proc.stdout))
        if vault_version == "latest":
            proc = subprocess.run(
                [vault_binary, "secrets", "enable", "-version=2", "-path=salt/", "kv"],
                env=env,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            ret = ProcessResult(
                exitcode=proc.returncode,
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
                    env=env,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
                ret = ProcessResult(
                    exitcode=proc.returncode,
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
                        env=env,
                        check=False,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                    )
                    ret = ProcessResult(
                        exitcode=proc.returncode,
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
                            env=env,
                            check=False,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True,
                        )
                        ret = ProcessResult(
                            exitcode=proc.returncode,
                            stdout=proc.stdout,
                            stderr=proc.stderr,
                            cmdline=proc.args,
                        )

            else:
                log.debug("Failed to enable kv-v2:\n%s", ret)
                pytest.fail("Could not enable kv-v2 {}".format(proc.stdout))
        yield vault_version
    finally:
        if container_started:
            ret = salt_call_cli.run(
                "state.single", "docker_container.stopped", name="vault"
            )
            assert ret.returncode == 0
            assert ret.data
            state_run = next(iter(ret.data.values()))
            assert state_run["result"] is True
            ret = salt_call_cli.run(
                "state.single", "docker_container.absent", name="vault"
            )
            assert ret.returncode == 0
            assert ret.data
            state_run = next(iter(ret.data.values()))
            assert state_run["result"] is True


@pytest.mark.slow_test
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


@pytest.mark.slow_test
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


@pytest.mark.slow_test
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


@pytest.mark.slow_test
def test_sdb_kv2_kvv2_path_local(salt_call_cli, vault_container_version):
    if vault_container_version not in ["1.3.1", "latest"]:
        pytest.skip("Test not applicable to vault {}".format(vault_container_version))
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


@pytest.mark.slow_test
def test_sdb_kv_dual_item(salt_call_cli, vault_container_version):
    if vault_container_version not in ["latest"]:
        pytest.skip("Test not applicable to vault {}".format(vault_container_version))
    ret = salt_call_cli.run("--local", "sdb.get", "sdb://sdbvault/salt/data/user1")
    assert ret.data
    assert ret.data == {"desc": "test user", "password": "p4ssw0rd"}
