import logging
import os

import pytest

import salt.states.file as filestate
import salt.utils.platform
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {filestate: {"__salt__": {}, "__opts__": {}}}


@pytest.fixture
def directory_name():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    return name


def test_pruned_clean(directory_name):
    with patch("os.path.isdir", return_value=False):
        ret = filestate.pruned(name=directory_name)
    assert ret == {
        "changes": {},
        "comment": "Directory {} is not present".format(directory_name),
        "name": directory_name,
        "result": True,
    }


def test_pruned_test(directory_name):
    with patch("os.path.isdir", return_value=True), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        ret = filestate.pruned(name=directory_name)
    assert ret == {
        "changes": {"deleted": directory_name},
        "comment": "Directory {} is set for removal".format(directory_name),
        "name": directory_name,
        "result": None,
    }


def test_pruned_success(directory_name):
    rmdir = MagicMock(return_value={"result": True})
    with patch("os.path.isdir", return_value=True), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(filestate.__salt__, {"file.rmdir": rmdir}):
        ret = filestate.pruned(name=directory_name)
    assert ret == {
        "changes": {"deleted": directory_name},
        "comment": "Removed directory {}".format(directory_name),
        "name": directory_name,
        "result": True,
    }
