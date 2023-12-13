import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux,
    pytest.mark.skipif(
        'grains["os_family"] != "Debian"',
        reason="Tests applicable only to Debian and Ubuntu",
    ),
]


def test_grains(grains):
    """
    Test to ensure that the lsb_distrib_xxxx grains are
    populated on Debian machines
    """
    assert "lsb_distrib_id" in grains
    assert "lsb_distrib_release" in grains
    assert "lsb_distrib_codename" in grains

    assert grains["lsb_distrib_id"] == grains["osfullname"]
    assert grains["lsb_distrib_release"] == grains["osrelease"]
    assert grains["lsb_distrib_codename"] == grains["oscodename"]
