"""
Test the bgp runner
"""
import pytest

import salt.runners.bgp as bgp

pytestmark = [
    pytest.mark.skipif(
        not bgp.HAS_NAPALM, reason="napalm module required for this test"
    )
]


@pytest.fixture
def configure_loader_modules():
    return {
        bgp: {
            "__opts__": {
                "optimization_order": [0, 1, 2],
                "renderer": "yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
            }
        }
    }


def test_neighbors():
    ret = bgp.neighbors()
    assert ret == []
