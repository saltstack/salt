"""
Tests using users formula
"""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests


@pytest.fixture(scope="module")
def formula_tag():
    return "0.48.8"


@pytest.fixture(scope="module")
def repo_url(formula_tag):
    return f"https://github.com/saltstack-formulas/users-formula/archive/refs/tags/v{formula_tag}.zip"


@pytest.fixture(scope="module")
def users_repo(state_tree, base_env_state_tree_root_dir, formula_tag, repo_url):
    local_filename = Path(repo_url.split("/")[-1])
    zip_path = state_tree / local_filename
    with requests.get(repo_url, allow_redirects=True, stream=True) as req:
        req.raise_for_status()
        with salt.utils.files.fopen(zip_path, "wb") as fho:
            for chunk in req.iter_content(chunk_size=8192):
                fho.write(chunk)
    with ZipFile(zip_path) as zip_obj:
        zip_obj.extractall(state_tree)
    extract_path = state_tree / f"users-formula-{formula_tag}"
    shutil.move(extract_path / "users", base_env_state_tree_root_dir)
    return str(base_env_state_tree_root_dir)


def test_users_formula(salt_call_cli, users_repo):
    # sudo
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "users.sudo",
        "test=True",
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "pkg_|-users_bash-package_|-bash_|-installed",
        "file_|-users_/etc/sudoers.d_|-/etc/sudoers.d_|-directory",
        "pkg_|-users_sudo-package_|-sudo_|-installed",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False
    # bashrc
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "users.bashrc",
        "test=True",
        "pillar=" + json.dumps({"users": {"stan": {"fullname": "Stan Lee"}}}),
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "group_|-users_stan_user_|-stan_|-present",
        "file_|-users_/etc/sudoers.d/stan_|-/etc/sudoers.d/stan_|-absent",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False
