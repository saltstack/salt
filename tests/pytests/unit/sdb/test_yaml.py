"""
Test case for the YAML SDB module
"""

import salt.sdb.yaml as sdb
from tests.support.mock import MagicMock, patch


def test_plaintext():
    """
    Retrieve a value from the top level of the dictionary
    """
    plain = {"foo": "bar"}
    with patch("salt.sdb.yaml._get_values", MagicMock(return_value=plain)):
        assert sdb.get("foo") == "bar"


def test_nested():
    """
    Retrieve a value from a nested level of the dictionary
    """
    plain = {"foo": {"bar": "baz"}}
    with patch("salt.sdb.yaml._get_values", MagicMock(return_value=plain)):
        assert sdb.get("foo:bar") == "baz"


def test_encrypted():
    """
    Assume the content is plaintext if GPG is not configured
    """
    plain = {"foo": "bar"}
    with patch("salt.sdb.yaml._decrypt", MagicMock(return_value=plain)):
        with patch("salt.sdb.yaml._get_values", MagicMock(return_value=None)):
            assert sdb.get("foo", profile={"gpg": True}) == "bar"
