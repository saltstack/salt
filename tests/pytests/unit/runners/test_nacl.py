"""
    Unit tests for the salt.runners.nacl module
"""

import salt.runners.nacl
from tests.support.mock import patch


def test_fips_mode():
    """
    Nacl runner doesn't load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.runners.nacl.__opts__", opts, create=True):
        ret = salt.runners.nacl.__virtual__()
        assert ret == (False, "nacl runner not available in FIPS mode")
