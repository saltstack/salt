import sys

import salt.grains.package


def test_grain_package_type(tmp_path):
    """
    Test grains.package_type for both package types
    """
    ret = salt.grains.package.package()["package"]
    if hasattr(sys, "RELENV"):
        assert ret == "onedir"
    else:
        assert ret == "system"
