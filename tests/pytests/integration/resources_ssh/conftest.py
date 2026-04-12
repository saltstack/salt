"""
Fixtures for SSH resource integration tests.

Spins up the shared session master, a module-scoped sshd, Pillar declaring one
SSH resource (``ssh-int-01``) pointing at that sshd, and a minion that manages
it.  This exercises :mod:`salt.resource.ssh` — including ``Single`` built from
minion opts, relenv, and ``cmd_block()`` — which plain salt-ssh integration
tests never touch (they run on the master only).
"""

from __future__ import annotations

import glob
import logging
import os
import pathlib
import platform
import shutil
import tempfile
import time

import pytest

# sshd usually lives in /usr/sbin, which is not always on a non-login PATH.
for _bindir in ("/usr/sbin", "/usr/local/sbin"):
    if os.path.isdir(_bindir) and _bindir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _bindir + os.pathsep + os.environ.get("PATH", "")

import salt.utils.relenv
from tests.conftest import FIPS_TESTRUN
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

SSH_RESOURCE_ID = "ssh-int-01"
MINION_ID = "ssh-resources-minion"


def _detect_kernel_and_arch():
    kernel = platform.system().lower()
    if kernel == "darwin":
        kernel = "darwin"
    elif kernel == "windows":
        kernel = "windows"
    else:
        kernel = "linux"

    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        os_arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        os_arch = "arm64"
    else:
        os_arch = machine
    return kernel, os_arch


@pytest.fixture(scope="session")
def relenv_tarball_for_ssh_resource():
    """
    Pre-resolve a relenv tarball path for populating the minion cache.

    ``salt.resource.ssh._relenv_path`` looks under
    ``<cachedir>/relenv/linux/<arch>/salt-relenv.tar.xz`` for ``x86_64`` or ``arm64``.
    """
    shared_cache = os.path.join(tempfile.gettempdir(), "salt_ssh_resource_int_relenv")
    os.makedirs(shared_cache, exist_ok=True)
    kernel, os_arch = _detect_kernel_and_arch()

    artifacts_glob = str(
        pathlib.Path("/salt/artifacts").joinpath(
            f"salt-*-onedir-{kernel}-{os_arch}.tar.xz"
        )
    )
    for path in glob.glob(artifacts_glob):
        if os.path.isfile(path):
            log.info("Using CI artifact relenv tarball: %s", path)
            return path

    try:
        path = salt.utils.relenv.gen_relenv(
            shared_cache, kernel=kernel, os_arch=os_arch
        )
        if path and os.path.isfile(path):
            log.info("Relenv tarball for SSH resource tests: %s", path)
            return path
    except (OSError, ValueError) as exc:
        log.warning("Could not build/download relenv tarball: %s", exc)
    return None


@pytest.fixture(scope="module")
def pillar_tree_ssh_resources(
    salt_master, sshd_server, sshd_config_dir, known_hosts_file
):
    """
    Pillar declaring ``resources.ssh.hosts`` for ``ssh-int-01`` → local sshd.
    """
    port = sshd_server.listen_port
    user = RUNTIME_VARS.RUNNING_TESTS_USER
    priv = str(sshd_config_dir / "client_key")

    top_file = f"""
    base:
      '{MINION_ID}':
        - ssh_resources_int
    """

    # Host blocks mirror roster-style auth; ignore_host_keys keeps the test simple.
    ssh_pillar = f"""
    resources:
      ssh:
        hosts:
          {SSH_RESOURCE_ID}:
            host: 127.0.0.1
            port: {port}
            user: {user}
            priv: {priv}
            ignore_host_keys: true
            timeout: 180
    """

    top_tempfile = salt_master.pillar_tree.base.temp_file("top.sls", top_file)
    pillar_tempfile = salt_master.pillar_tree.base.temp_file(
        "ssh_resources_int.sls", ssh_pillar
    )
    with top_tempfile, pillar_tempfile:
        yield


@pytest.fixture(scope="module")
def salt_minion_ssh_resources(
    salt_master,
    pillar_tree_ssh_resources,
    relenv_tarball_for_ssh_resource,
):
    assert salt_master.is_running()

    config_overrides = {
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        # Match resources/dummy integration: thread pool, resource race coverage.
        "multiprocessing": False,
    }

    factory = salt_master.salt_minion_daemon(
        MINION_ID,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )

    with factory.started(start_timeout=120):
        cachedir = factory.config["cachedir"]
        _kernel, os_arch = _detect_kernel_and_arch()
        relenv_subdir = os.path.join(cachedir, "relenv", "linux", os_arch)
        os.makedirs(relenv_subdir, exist_ok=True)
        dest = os.path.join(relenv_subdir, "salt-relenv.tar.xz")
        if relenv_tarball_for_ssh_resource and os.path.isfile(
            relenv_tarball_for_ssh_resource
        ):
            shutil.copyfile(relenv_tarball_for_ssh_resource, dest)
            log.info("Installed relenv tarball for minion at %s", dest)
        else:
            log.warning(
                "No relenv tarball available — SSH resource tests that need relenv may fail"
            )

        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True, _timeout=120)
        assert ret.returncode == 0, ret
        assert ret.data is True, ret

        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret

        time.sleep(3)
        yield factory


@pytest.fixture(scope="module")
def salt_call_ssh_resource(salt_minion_ssh_resources):
    assert salt_minion_ssh_resources.is_running()
    return salt_minion_ssh_resources.salt_call_cli(timeout=120)


@pytest.fixture(scope="module")
def salt_cli_ssh_resource(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli(timeout=120)
