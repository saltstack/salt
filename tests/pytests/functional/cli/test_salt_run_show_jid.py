"""
Tests for salt-run with show_jid
"""

import logging
import re

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def salt_master(salt_factories):
    """
    Salt master with `show_jid: True`
    """
    config_defaults = {
        "show_jid": True,
    }
    salt_master = salt_factories.salt_master_daemon(
        "salt-run-show-jid-master", defaults=config_defaults
    )
    with salt_master.started():
        yield salt_master


@pytest.fixture(scope="module")
def salt_run_cli(salt_master):
    """
    The ``salt-run`` CLI as a fixture against the running master
    """
    assert salt_master.is_running()
    return salt_master.salt_run_cli(timeout=30)


def test_salt_run_show_jid(salt_run_cli):
    """
    Test that jid is output
    """
    ret = salt_run_cli.run("test.stdout_print")
    assert re.match(r"jid: \d+", ret.stdout)
