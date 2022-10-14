import collections
import textwrap

import pytest

import salt.roster.sshconfig as sshconfig
from tests.support.mock import mock_open, patch


@pytest.fixture
def target_abc():
    return collections.OrderedDict(
        [
            ("user", "user.mcuserface"),
            ("priv", "~/.ssh/id_rsa_abc"),
            ("host", "abc.asdfgfdhgjkl.com"),
        ]
    )


@pytest.fixture
def target_abc123():
    return collections.OrderedDict(
        [
            ("user", "user.mcuserface"),
            ("priv", "~/.ssh/id_rsa_abc"),
            ("host", "abc123.asdfgfdhgjkl.com"),
        ]
    )


@pytest.fixture
def target_def():
    return collections.OrderedDict(
        [
            ("user", "user.mcuserface"),
            ("priv", "~/.ssh/id_rsa_def"),
            ("host", "def.asdfgfdhgjkl.com"),
        ]
    )


@pytest.fixture
def all_(target_abc, target_abc123, target_def):
    return {
        "abc.asdfgfdhgjkl.com": target_abc,
        "abc123.asdfgfdhgjkl.com": target_abc123,
        "def.asdfgfdhgjkl.com": target_def,
    }


@pytest.fixture
def abc_glob(target_abc, target_abc123):
    return {
        "abc.asdfgfdhgjkl.com": target_abc,
        "abc123.asdfgfdhgjkl.com": target_abc123,
    }


@pytest.fixture
def mock_fp():
    sample_ssh_config = textwrap.dedent(
        """
    Host *
        User user.mcuserface

    Host abc*
        IdentityFile ~/.ssh/id_rsa_abc

    Host def*
        IdentityFile  ~/.ssh/id_rsa_def

    Host abc.asdfgfdhgjkl.com
        HostName 123.123.123.123

    Host abc123.asdfgfdhgjkl.com
        HostName 123.123.123.124

    Host def.asdfgfdhgjkl.com
        HostName      234.234.234.234
    """
    )

    return mock_open(read_data=sample_ssh_config)


@pytest.fixture
def configure_loader_modules():
    return {sshconfig: {}}


def test_all(mock_fp, all_):
    with patch("salt.utils.files.fopen", mock_fp):
        with patch("salt.roster.sshconfig._get_ssh_config_file"):
            targets = sshconfig.targets("*")
    assert targets == all_


def test_abc_glob(mock_fp, abc_glob):
    with patch("salt.utils.files.fopen", mock_fp):
        with patch("salt.roster.sshconfig._get_ssh_config_file"):
            targets = sshconfig.targets("abc*")
    assert targets == abc_glob
