"""
    Unit tests for the salt.pillar.nacl module
"""

import salt.pillar.nacl
from tests.support.mock import patch


def test_fips_mode():
    """
    Nacl pillar doesn't load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.pillar.nacl.__opts__", opts, create=True):
        ret = salt.pillar.nacl.__virtual__()
        assert ret == (False, "nacl pillar data not available in FIPS mode")
