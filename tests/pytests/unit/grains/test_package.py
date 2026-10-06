import os

import salt.grains.package


def test_grain_package_type():
    """
    Test grains.package_type for both package types
    """
    ret = salt.grains.package.package()["package"]
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        assert ret == "pip"
    else:
        assert ret == "onedir"
