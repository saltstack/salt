"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.key
"""

import os.path

import pytest

import salt.modules.key as key
import salt.utils.crypt
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {key: {}}


def test_finger():
    """
    Test for finger
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(salt.utils.crypt, "pem_finger", return_value="A"):
            with patch.dict(
                key.__opts__,
                {"pki_dir": MagicMock(return_value="A"), "hash_type": "sha256"},
            ):
                assert key.finger() == "A"


def test_finger_master():
    """
    Test for finger
    """
    with patch.object(os.path, "join", return_value="A"):
        with patch.object(salt.utils.crypt, "pem_finger", return_value="A"):
            with patch.dict(key.__opts__, {"pki_dir": "A", "hash_type": "sha256"}):
                assert key.finger_master() == "A"
