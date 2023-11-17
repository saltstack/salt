import logging

import pytest

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_unless_on_linux,
    pytest.mark.skipif(
        'grains["os_family"] != "Debian"',
        reason="Tests applicable only to Debian and Ubuntu",
    ),
]


def test_grains(grains):
    log.warning(f"DGM test_grains '{grains}'")

    assert "lsb_distrib_id" in grains
    assert "lsb_distrib_release" in grains
    assert "lsb_distrib_codename" in grains

    assert grains["lsb_distrib_id"] == grains["osfullname"]
    assert grains["lsb_distrib_release"] == grains["osrelease"]
    assert grains["lsb_distrib_codename"] == grains["oscodename"]
