import sys

import pytest


@pytest.fixture(scope="module")
def grains(modules):
    return modules.grains


def test_grains_items(grains):
    """
    Test running grains.items and assert
    certain information is included in
    the return
    """
    ret = grains.items()
    if hasattr(sys, "RELENV"):
        assert ret["package"] == "onedir"
    else:
        assert ret["package"] == "system"

    for key in ["num_cpus", "cpu_model", "os_family"]:
        assert key in ret.keys()
