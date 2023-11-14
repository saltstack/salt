"""
Tests for MasterMinion class
"""

import logging
import os
import pathlib

import pytest

import salt.minion

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def minion_config_overrides(master_opts):
    """Configure minion to use same root_dir and config path as master."""
    root_dir = pathlib.Path(master_opts["root_dir"])
    conf_file = root_dir / "conf" / "minion"
    yield {"conf_file": str(conf_file), "root_dir": str(root_dir)}


@pytest.fixture
def minion_d_include_value(minion_opts):
    """Create minion.d/test.conf with 'minion_d_value' config option."""
    conf_dir = pathlib.Path(minion_opts["conf_file"]).parent
    minion_include_dir = (conf_dir / minion_opts["default_include"]).parent
    test_conf = minion_include_dir / "test.conf"
    os.makedirs(minion_include_dir)
    with salt.utils.files.fopen(test_conf, "w") as test_conf:
        test_conf.write("minion_d_value: True")


def test_issue_64219_masterminion_no_minion_d_include(
    master_opts, minion_d_include_value
):
    """Create MasterMinion and test it doesn't get config from 'minion.d/*.conf'."""

    mminion = salt.minion.MasterMinion(master_opts)
    assert "minion_d_value" not in mminion.opts
