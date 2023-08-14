import os

import salt.utils.package


def test_pkg_type():
    ret = salt.utils.package.pkg_type()
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        assert ret == "pip"
    else:
        assert ret == "onedir"
