"""
Tests using docker formula
"""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests


@pytest.fixture(scope="module")
def formula_tag():
    return "2.4.2"


@pytest.fixture(scope="module")
def repo_url(formula_tag):
    return f"https://github.com/saltstack-formulas/docker-formula/archive/refs/tags/v{formula_tag}.zip"


@pytest.fixture(scope="module")
def docker_repo(state_tree, base_env_state_tree_root_dir, formula_tag, repo_url):
    local_filename = Path(repo_url.split("/")[-1])
    zip_path = state_tree / local_filename
    with requests.get(repo_url, allow_redirects=True, stream=True) as req:
        req.raise_for_status()
        with salt.utils.files.fopen(zip_path, "wb") as fho:
            for chunk in req.iter_content(chunk_size=8192):
                fho.write(chunk)
    with ZipFile(zip_path) as zip_obj:
        zip_obj.extractall(state_tree)
    extract_path = state_tree / f"docker-formula-{formula_tag}"
    shutil.move(extract_path / "docker", base_env_state_tree_root_dir)
    return str(base_env_state_tree_root_dir)


def test_docker_formula(salt_call_cli, docker_repo):
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "docker",
        "test=True",
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "archive_|-docker-software-docker-archive-install_|-/usr/local/docker-19.03.9/bin/_|-extracted",
        "cmd_|-docker-software-docker-archive-install-managed-service_|-systemctl daemon-reload_|-run",
        "file_|-docker-compose-software-binary-install-symlink-docker-compose_|-/usr/local/bin/docker-compose_|-symlink",
        "file_|-docker-compose-software-binary-install_|-/usr/local/docker-compose-latest/bin//docker-compose_|-managed",
        "file_|-docker-software-daemon-file-managed-daemon_file_|-/etc/docker/daemon.json_|-absent",
        "file_|-docker-software-docker-archive-install-file-directory_|-/var/lib/docker_|-directory",
        "file_|-docker-software-docker-archive-install-managed-service_|-/usr/lib/systemd/system/docker.service_|-managed",
        "file_|-docker-software-docker-archive-install-symlink-containerd-shim_|-/usr/local/bin/containerd-shim_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-containerd_|-/usr/local/bin/containerd_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-ctr_|-/usr/local/bin/ctr_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-docker-init_|-/usr/local/bin/docker-init_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-docker-proxy_|-/usr/local/bin/docker-proxy_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-docker_|-/usr/local/bin/docker_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-dockerd_|-/usr/local/bin/dockerd_|-symlink",
        "file_|-docker-software-docker-archive-install-symlink-runc_|-/usr/local/bin/runc_|-symlink",
        "file_|-docker-software-docker-archive-install_|-/usr/local/docker-19.03.9/bin/_|-directory",
        "pkg_|-docker-compose-software-binary-install_|-python-docker_|-installed",
        "pkg_|-docker-compose-software-binary-install_|-python-pip_|-installed",
        "pkg_|-docker-software-docker-archive-install_|-python-docker_|-installed",
        "pkg_|-docker-software-docker-archive-install_|-python-pip_|-installed",
        "service_|-docker-software-service-running-docker_|-docker_|-running",
        "service_|-docker-software-service-running-unmasked_|-docker_|-unmasked",
        "service_|-docker-software-service-running-docker-fail-notify_|-docker_|-enabled",
        "test_|-docker-compose-package-install-other_|-docker-compose-package-install-other_|-show_notification",
        "test_|-docker-software-desktop-install-other_|-docker-software-desktop-install-other_|-show_notification",
        "test_|-docker-software-package-install-other_|-docker-software-package-install-other_|-show_notification",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False

    state_ids = [
        "test_|-docker-software-service-running-docker-fail-notify_|-docker-software-service-running-docker-fail-notify_|-fail_without_changes",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is False
