"""
Unit tests for the LGPO module
"""

import os
import platform

import pytest
from packaging import version

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


def _parse_platform_version():
    if platform.system() != "Windows":
        # Test only applies to windows but pytestmark is not getting
        # evaluated soon enough
        return True
    return version.parse(platform.version()) < version.parse("10.0.16299")


@pytest.fixture(scope="module")
def lgpo(modules):
    return modules.lgpo


# The "Allow Online Tips" policy only became available in version 10.0.16299
@pytest.mark.skipif(
    _parse_platform_version(),
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


def test_61859(lgpo):
    expected = (
        'ADMX policy name/id "Pol_CipherSuiteOrder" is used in multiple ADMX files.\n'
        "Try one of the following names:\n"
        " - Lanman Server\\Network\\Cipher suite order\n"
        " - Lanman Workstation\\Network\\Cipher suite order"
    )
    result = lgpo.get_policy_info(
        policy_name="Pol_CipherSuiteOrder",
        policy_class="machine",
    )
    assert result["message"] == expected


_TS_SERVER_ADMX = r"C:\Windows\PolicyDefinitions\TerminalServer-Server.admx"


@pytest.mark.skipif(
    not os.path.exists(_TS_SERVER_ADMX),
    reason="TerminalServer-Server.admx only present on Windows Server editions",
)
def test_62732_duplicate_policy_identical_paths(lgpo):
    """
    On Windows Server, TerminalServer.admx and TerminalServer-Server.admx
    both define "Do not allow Clipboard redirection" with the same full path.
    get_policy_info should resolve it as a single unambiguous policy rather
    than returning a "multiple policies" error.
    """
    result = lgpo.get_policy_info(
        policy_name="Do not allow Clipboard redirection",
        policy_class="Machine",
    )
    assert result["policy_found"] is True
    assert not result["message"]
    assert result["policy_name"] == "Do not allow Clipboard redirection"
