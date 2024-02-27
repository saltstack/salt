"""
Grains include tests
"""

import os


def test_grains_package(salt_call_cli):
    """
    An integration test for the package grain
    is a bit overkill, but it is necessary currently
    because the onedir package is only tested with
    integration tests, so I want to ensure its working
    correctly. Once the onedir package is tested with unit
    and functional tests this test can be removed since
    there is plenty of test coverage in both unit and functional
    for this new grain.
    """
    ret = salt_call_cli.run("grains.get", "package")
    assert ret.returncode == 0
    assert ret.data
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        assert ret.data == "pip"
    else:
        assert ret.data == "onedir"
