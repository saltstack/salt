"""
test for pillar file_tree.py
"""

import os
import pathlib

import pytest

import salt.pillar.file_tree as file_tree
import salt.utils.files
import salt.utils.stringutils
from tests.support.mock import MagicMock, patch


@pytest.fixture
def minion_id():
    return "test-host"


@pytest.fixture
def base_pillar_content():
    return {"files": {"hostfile": b"base", "groupfile": b"base"}}


@pytest.fixture
def dev_pillar_content():
    return {
        "files": {
            "hostfile": b"base",
            "groupfile": b"dev2",
            "hostfile1": b"dev1",
            "groupfile1": b"dev1",
            "hostfile2": b"dev2",
        }
    }


@pytest.fixture
def parent_pillar_content():
    return {"files": {"hostfile": b"base", "groupfile": b"base", "hostfile2": b"dev2"}}


@pytest.fixture
def pillar_path(tmp_path):
    return tmp_path / "file_tree"


@pytest.fixture
def configure_loader_modules(tmp_path, minion_id, pillar_path):
    cachedir = tmp_path / "cachedir"
    nodegroup_path = pathlib.Path("nodegroups", "test-group", "files")
    host_path = pathlib.Path("hosts", minion_id, "files")
    file_data = {
        (pillar_path / "base" / host_path / "hostfile"): "base",
        (pillar_path / "dev1" / host_path / "hostfile1"): "dev1",
        (pillar_path / "dev2" / host_path / "hostfile2"): "dev2",
        (pillar_path / "base" / nodegroup_path / "groupfile"): "base",
        (pillar_path / "dev1" / nodegroup_path / "groupfile1"): "dev1",
        (pillar_path / "dev2" / nodegroup_path / "groupfile"): "dev2",  # test merging
    }
    for filename in file_data:
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(salt.utils.stringutils.to_str(file_data[filename]))

    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(return_value={"minions": [minion_id], "missing": []}),
    ):
        yield {
            file_tree: {
                "__opts__": {
                    "cachedir": cachedir,
                    "pillar_roots": {
                        "base": [str(pillar_path / "base")],
                        "dev": [
                            str(pillar_path / "base"),
                            str(pillar_path / "dev1"),
                            str(pillar_path / "dev2"),
                        ],
                        "parent": [
                            str(pillar_path / "base" / "sub1"),
                            str(pillar_path / "dev2" / "sub"),
                            str(pillar_path / "base" / "sub2"),
                        ],
                    },
                    "pillarenv": "base",
                    "nodegroups": {"test-group": [minion_id]},
                    "optimization_order": [0, 1, 2],
                    "file_buffer_size": 262144,
                    "file_roots": {"base": "", "dev": "", "parent": ""},
                    "extension_modules": "",
                    "renderer": "yaml_jinja",
                    "renderer_blacklist": [],
                    "renderer_whitelist": [],
                }
            }
        }


def test_absolute_path(base_pillar_content, minion_id, pillar_path):
    """
    check file tree is imported correctly with an absolute path
    """
    absolute_path = pillar_path / "base"
    mypillar = file_tree.ext_pillar(minion_id, None, str(absolute_path))
    assert base_pillar_content == mypillar

    with patch.dict(file_tree.__opts__, {"pillarenv": "dev"}):
        mypillar = file_tree.ext_pillar(minion_id, None, absolute_path)
        assert base_pillar_content == mypillar


def test_relative_path(base_pillar_content, dev_pillar_content, minion_id):
    """
    check file tree is imported correctly with a relative path
    """
    mypillar = file_tree.ext_pillar(minion_id, None, ".")
    assert base_pillar_content == mypillar

    with patch.dict(file_tree.__opts__, {"pillarenv": "dev"}):
        mypillar = file_tree.ext_pillar(minion_id, None, ".")
        assert dev_pillar_content == mypillar


def test_parent_path(parent_pillar_content, minion_id):
    """
    check if file tree is merged correctly with a .. path
    """
    with patch.dict(file_tree.__opts__, {"pillarenv": "parent"}):
        mypillar = file_tree.ext_pillar(minion_id, None, "..")
        assert parent_pillar_content == mypillar


def test_no_pillarenv(minion_id, caplog):
    """
    confirm that file_tree yells when pillarenv is missing for a relative path
    """
    with patch.dict(file_tree.__opts__, {"pillarenv": None}):
        mypillar = file_tree.ext_pillar(minion_id, None, ".")
        assert {} == mypillar

        for record in caplog.records:
            if record.levelname == "ERROR" and "pillarenv is not set" in record.message:
                break
        else:
            raise AssertionError("Did not find error message")


def test_file_tree_bytes(pillar_path, minion_id, base_pillar_content):
    """
    test file_tree pillar returns bytes
    """
    absolute_path = os.path.join(pillar_path, "base")
    mypillar = file_tree.ext_pillar(minion_id, None, absolute_path)
    assert base_pillar_content == mypillar

    with patch.dict(file_tree.__opts__, {"pillarenv": "dev"}):
        mypillar = file_tree.ext_pillar(minion_id, None, absolute_path)
        assert mypillar["files"]["groupfile"] == b"base"
