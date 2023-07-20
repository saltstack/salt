"""
Tests using docker formula
"""
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
import requests

import salt.utils.files


@pytest.fixture(scope="module")
def modules(loaders):
    return loaders.modules


@pytest.fixture(scope="module")
def formula_tag():
    return "2.4.2"


@pytest.fixture(scope="module")
def repo_url(formula_tag):
    return f"https://github.com/saltstack-formulas/docker-formula/archive/refs/tags/v{formula_tag}.zip"


@pytest.fixture(scope="module", autouse=True)
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


def test_docker_formula(modules):
    ret = modules.state.sls("docker", test=True)
    for staterun in ret:
        assert not staterun.result.failed
