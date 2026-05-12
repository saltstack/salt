"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.win_ip
"""

import pytest

import salt.modules.win_ip as win_ip
from salt.exceptions import SaltInvocationError


def test_get_subnet_length():
    """
    Test get subnet length is correct.
    """
    assert win_ip.get_subnet_length("255.255.255.0") == 24
    pytest.raises(SaltInvocationError, win_ip.get_subnet_length, "255.255.0")
