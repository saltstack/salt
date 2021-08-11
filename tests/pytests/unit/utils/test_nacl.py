"""
    Unit tests for the salt.utils.nacl module
"""

import salt.utils.nacl
from tests.support.mock import patch


def test_fips_mode():
    """
    Nacl pillar doesn't load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.utils.nacl.__opts__", opts, create=True):
        ret = salt.utils.nacl.__virtual__()
        assert ret == (False, "nacl utils not available in FIPS mode")
