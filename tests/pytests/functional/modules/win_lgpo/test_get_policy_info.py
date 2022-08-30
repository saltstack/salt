"""
Unit tests for the LGPO module
"""

import platform

import pytest
from packaging import version

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


# The "Allow Online Tips" policy only became available in version 10.0.16299
@pytest.mark.skipif(
    version.parse(platform.version()) < version.parse("10.0.16299"),
    reason="Policy only available on 10.0.16299 or later",
)
def test_62058_whitespace(lgpo):
    result = lgpo.get_policy_info("Allow Online Tips", "machine")
    for element in result["policy_elements"]:
        if "element_aliases" in element:
            assert (
                "Allow Settings to retrieve online tips." in element["element_aliases"]
            )
            return
    assert False
