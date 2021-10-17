import pytest
import salt.states.virt as virt
from tests.support.mock import MagicMock


class LibvirtMock(MagicMock):  # pylint: disable=too-many-ancestors
    """
    Libvirt library mock
    """

    class libvirtError(Exception):
        """
        libvirtError mock
        """

        def __init__(self, msg):
            super().__init__(msg)
            self.msg = msg

        def get_error_message(self):
            return self.msg


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {virt: {"libvirt": LibvirtMock()}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


@pytest.fixture(params=[True, False], ids=["test", "notest"])
def test(request):
    """
    Run the test with both True and False test values
    """
    return request.param
