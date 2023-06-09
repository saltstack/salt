import sys

import salt.utils.package


def test_pkg_type():
    ret = salt.utils.package.pkg_type()
    if hasattr(sys, "RELENV"):
        assert ret == "onedir"
    else:
        assert ret == "system"
