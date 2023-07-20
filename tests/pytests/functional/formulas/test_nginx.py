"""
Tests using nginx formula
"""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests


@pytest.fixture(scope="module")
def formula_tag():
    return "2.8.1"


@pytest.fixture(scope="module")
def repo_url(formula_tag):
    return f"https://github.com/saltstack-formulas/nginx-formula/archive/refs/tags/v{formula_tag}.zip"


@pytest.fixture(scope="module")
def nginx_repo(state_tree, base_env_state_tree_root_dir, formula_tag, repo_url):
    local_filename = Path(repo_url.split("/")[-1])
    zip_path = state_tree / local_filename
    with requests.get(repo_url, allow_redirects=True, stream=True) as req:
        req.raise_for_status()
        with salt.utils.files.fopen(zip_path, "wb") as fho:
            for chunk in req.iter_content(chunk_size=8192):
                fho.write(chunk)
    with ZipFile(zip_path) as zip_obj:
        zip_obj.extractall(state_tree)
    extract_path = state_tree / f"nginx-formula-{formula_tag}"
    shutil.move(extract_path / "nginx", base_env_state_tree_root_dir)
    return str(base_env_state_tree_root_dir)


def test_formula(salt_call_cli, nginx_repo):
    out = salt_call_cli.run(
        "--local",
        "state.sls",
        "nginx",
        "test=True",
    )
    ret = json.loads(str(out.stdout))
    state_ids = [
        "file_|-nginx_config_|-/etc/nginx/nginx.conf_|-managed",
        "file_|-nginx_server_available_dir_|-/etc/nginx/sites-available_|-directory",
        "file_|-nginx_server_enabled_dir_|-/etc/nginx/sites-enabled_|-directory",
        "file_|-prepare_certificates_path_dir_|-/etc/nginx/ssl_|-directory",
        "pkg_|-nginx_install_|-nginx_|-installed",
        "service_|-listener_nginx_service_|-nginx_|-mod_watch",
        "service_|-nginx_service_|-nginx_|-running",
    ]
    for state_id in state_ids:
        assert ret["local"][state_id]["result"] is not False
