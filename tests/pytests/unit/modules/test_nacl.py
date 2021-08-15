"""
    Unit tests for the salt.modules.nacl module
"""

import salt.modules.nacl
from tests.support.mock import patch


def test_fips_mode():
    """
    Nacl module does not load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.modules.nacl.__opts__", opts, create=True):
        ret = salt.modules.nacl.__virtual__()
        assert ret == (False, "nacl module not available in FIPS mode")
