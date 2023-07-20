"""
Tests using salt formula
"""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests


@pytest.fixture(scope="module")
def formula_tag():
    return "1.12.0"


@pytest.fixture(scope="module")
def repo_url(formula_tag):
    return f"https://github.com/saltstack-formulas/salt-formula/archive/refs/tags/v{formula_tag}.zip"


@pytest.fixture(scope="module")
def salt_repo(state_tree, base_env_state_tree_root_dir, formula_tag, repo_url):
    local_filename = Path(repo_url.split("/")[-1])
    zip_path = state_tree / local_filename
    with requests.get(repo_url, allow_redirects=True, stream=True) as req:
        req.raise_for_status()
        with salt.utils.files.fopen(zip_path, "wb") as fho:
            for chunk in req.iter_content(chunk_size=8192):
                fho.write(chunk)
    with ZipFile(zip_path) as zip_obj:
        zip_obj.extractall(state_tree)
    extract_path = state_tree / f"salt-formula-{formula_tag}"
    shutil.move(extract_path / "salt", base_env_state_tree_root_dir)
    return str(base_env_state_tree_root_dir)


def test_salt_formula(salt_call_cli, salt_repo):
    # Master Formula
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "salt.master",
        "test=True",
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "pkg_|-salt-master_|-salt_|-installed",
        "file_|-salt-master_|-/etc/salt/master.d_|-recurse",
        "file_|-remove-old-master-conf-file_|-/etc/salt/master.d/_defaults.conf_|-absent",
        "service_|-salt-master_|-salt-master_|-running",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False

    # Minion Formula
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "salt.minion",
        "test=True",
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "pkg_|-salt-minion_|-salt_|-installed",
        "file_|-salt-minion_|-/etc/salt/minion.d_|-recurse",
        "file_|-remove-old-minion-conf-file_|-/etc/salt/minion.d/_defaults.conf_|-absent",
        "cmd_|-salt-minion_|-salt-call --local service.restart salt-minion --out-file /dev/null_|-run",
        "file_|-permissions-minion-config_|-/etc/salt/minion_|-managed",
        "file_|-salt-minion-pki-dir_|-/etc/salt/pki/minion_|-directory",
        "file_|-permissions-minion.pem_|-/etc/salt/pki/minion/minion.pem_|-managed",
        "file_|-permissions-minion.pub_|-/etc/salt/pki/minion/minion.pub_|-managed",
        "service_|-salt-minion_|-salt-minion_|-running",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False
