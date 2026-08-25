import hashlib
from textwrap import dedent

import pytest

import salt.modules.pdbedit as pdbedit
from tests.support.mock import MagicMock, patch

try:
    hashlib.new("md4", "".encode("utf-16le"))
    MD4_SUPPORTED = True
except ValueError:
    MD4_SUPPORTED = False


@pytest.fixture
def configure_loader_modules():
    return {pdbedit: {}}


@pytest.mark.parametrize("verbose", [True, False])
def test_when_no_users_returned_no_data_should_be_returned(verbose):
    expected_users = {} if verbose else []
    with patch.dict(
        pdbedit.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"stdout": "", "stderr": "", "retcode": 0}
            )
        },
    ):
        actual_users = pdbedit.list_users(verbose=verbose)

    assert actual_users == expected_users


def test_when_verbose_and_retcode_is_nonzero_output_should_be_had():
    expected_stderr = "this is something fnord"
    with patch.dict(
        pdbedit.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"stdout": "", "stderr": expected_stderr, "retcode": 1}
            )
        },
    ), patch("salt.modules.pdbedit.log.error", autospec=True) as fake_error_log:
        pdbedit.list_users(verbose=True)
        actual_error = fake_error_log.mock_calls[0].args[0]
        assert actual_error == expected_stderr


def test_when_verbose_and_single_good_output_expected_data_should_be_parsed():
    expected_data = {
        "roscivs": {
            "unix username": "roscivs",
            "nt username": "bottia",
            "full name": "Roscivs Bottia",
            "user sid": "42",
            "primary group sid": "99",
            "home directory": r"\\samba\roscivs",
            "account desc": "separators! xxx so long and thanks for all the fish",
            "logoff time": "Sat, 14 Aug 2010 15:06:39 UTC",
            "kickoff time": "Sat, 14 Aug 2010 15:06:39 UTC",
            "password must change": "never",
        }
    }
    pdb_output = dedent(
        r"""
        Unix username:        roscivs
        NT username:          bottia
        User SID:             42
        Primary Group SID:    99
        Full Name:            Roscivs Bottia
        Home Directory:       \\samba\roscivs
        Account desc:         separators! xxx so long and thanks for all the fish
        Logoff time:          Sat, 14 Aug 2010 15:06:39 UTC
        Kickoff time:         Sat, 14 Aug 2010 15:06:39 UTC
        Password must change: never
        """
    ).strip()

    with patch.dict(
        pdbedit.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"stdout": pdb_output, "stderr": "", "retcode": 0}
            )
        },
    ):
        actual_data = pdbedit.list_users(verbose=True)
        assert actual_data == expected_data


def test_when_verbose_and_multiple_records_present_data_should_be_correctly_parsed():
    expected_data = {
        "roscivs": {
            "unix username": "roscivs",
            "nt username": "bottia",
            "user sid": "42",
        },
        "srilyk": {
            "unix username": "srilyk",
            "nt username": "srilyk",
            "account desc": "trololollol",
            "user sid": "99",
        },
        "jewlz": {
            "unix username": "jewlz",
            "nt username": "flutterbies",
            "user sid": "4",
        },
    }
    pdb_output = dedent(
        """
        -------------
        Unix username:        roscivs
        NT username:          bottia
        User SID:             42
        -------------
        Unix username:        srilyk
        NT username:          srilyk
        User SID:             99
        Account desc:         trololol\x1dlol
        -------------
        Unix username:        jewlz
        NT username:          flutterbies
        User SID:             4
        -------------
        -------------
        -------------
        """
    ).strip()

    with patch.dict(
        pdbedit.__salt__,
        {
            "cmd.run_all": MagicMock(
                return_value={"stdout": pdb_output, "stderr": "", "retcode": 0}
            )
        },
    ):
        actual_data = pdbedit.list_users(verbose=True)
        assert actual_data == expected_data


@pytest.mark.skipif(not MD4_SUPPORTED, reason="Requires md4")
def test_create_with_existing_user_updates_password():
    with patch(
        "salt.modules.pdbedit.list_users", MagicMock(return_value=["Foo"])
    ), patch(
        "salt.modules.pdbedit.get_user",
        MagicMock(return_value={"nt hash": "old value"}),
    ), patch.dict(
        pdbedit.__salt__, {"cmd.run_all": MagicMock(return_value={"retcode": 0})}
    ):
        ret = pdbedit.create("Foo", "secret")
        assert {"Foo": "updated"} == ret
