"""
unittests for terraform roster
"""
import pathlib

import pytest

from salt.roster import terraform
from salt.utils import roster_matcher
from tests.support.mock import patch


@pytest.fixture
def roster_file():
    return pathlib.Path(__file__).parent / "terraform.data" / "terraform.tfstate"


@pytest.fixture
def roster_file_new():
    return pathlib.Path(__file__).parent / "terraform.data" / "terraform-new.tfstate"


@pytest.fixture
def pki_dir():
    return pathlib.Path(__file__).parent / "terraform.data"


@pytest.fixture
def configure_loader_modules(roster_file, pki_dir):
    # opts = salt.config.master_config(
    #     os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
    # )
    # utils = salt.loader.utils(opts, whitelist=["roster_matcher"])
    return {
        terraform: {
            "__utils__": {
                "roster_matcher.targets": roster_matcher.targets,
            },
            "__opts__": {
                "roster_file": str(roster_file),
                "pki_dir": str(pki_dir),
            },
        },
        roster_matcher: {},
    }


def test_default_output(pki_dir):
    """
    Test the output of a fixture tfstate file which contains libvirt
    resources.
    """
    expected_result = {
        "db0": {
            "host": "192.168.122.174",
            "user": "root",
            "passwd": "dbpw",
            "tty": True,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
        "db1": {
            "host": "192.168.122.190",
            "user": "root",
            "passwd": "dbpw",
            "tty": True,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
        "web0": {
            "host": "192.168.122.106",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
        "web1": {
            "host": "192.168.122.235",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
    }

    ret = terraform.targets("*")
    assert expected_result == ret


def test_default_matching(pki_dir):
    """
    Test the output of a fixture tfstate file which contains libvirt
    resources using matching
    """
    expected_result = {
        "web0": {
            "host": "192.168.122.106",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
        "web1": {
            "host": "192.168.122.235",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
    }

    ret = terraform.targets("*web*")
    assert expected_result == ret


def test_defaults_new(pki_dir, roster_file_new):
    """
    Test the output of a fixture tfstate file which contains libvirt
    resources using matching
    """
    expected_result = {
        "web0": {
            "host": "192.168.122.106",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
        "web1": {
            "host": "192.168.122.107",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
    }

    with patch.dict(terraform.__opts__, {"roster_file": str(roster_file_new)}):
        ret = terraform.targets("*")
        assert expected_result == ret


def test_defaults_new_matching(pki_dir, roster_file_new):
    """
    Test the output of a fixture tfstate file which contains libvirt
    resources using matching
    """
    expected_result = {
        "web1": {
            "host": "192.168.122.107",
            "user": "root",
            "passwd": "linux",
            "timeout": 22,
            "priv": str(pki_dir / "ssh" / "salt-ssh.rsa"),
        },
    }

    with patch.dict(terraform.__opts__, {"roster_file": str(roster_file_new)}):
        ret = terraform.targets("*1")
        assert expected_result == ret


def test_correct_handler_called_old():
    old_mock = patch.object(terraform, "_do__parse_old_state_file")
    new_mock = patch.object(terraform, "_do_parse_new_state_file")
    with old_mock as _old, new_mock as _new:
        terraform.targets("*")
        _old.assert_called_once()
        _new.assert_not_called()


def test_correct_handler_called_new(roster_file_new):
    old_mock = patch.object(terraform, "_do__parse_old_state_file")
    new_mock = patch.object(terraform, "_do_parse_new_state_file")
    with old_mock as _old, new_mock as _new:
        with patch.dict(terraform.__opts__, {"roster_file": str(roster_file_new)}):
            terraform.targets("*")
            _old.assert_not_called()
            _new.assert_called_once()
