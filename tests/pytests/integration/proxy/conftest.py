import pytest
from tests.support.helpers import PRE_PYTEST_SKIP_REASON


@pytest.fixture(autouse=True)
def skip_pre_pytest_platforms(grains):
    os = grains["os"]
    os_major_version = int(grains.get("osmajorrelease") or 0)
    centos_7 = os == "CentOS" and os_major_version == 7
    ubuntu_16 = os == "Ubuntu" and os_major_version == 16
    if not centos_7 and not ubuntu_16:
        pytest.skip(PRE_PYTEST_SKIP_REASON)
