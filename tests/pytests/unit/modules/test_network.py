import threading

import pytest
import salt.modules.network as networkmod
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {networkmod: {}}


@pytest.fixture
def socket_errors():
    # Not sure what kind of errors could be returned by getfqdn or
    # gethostbyaddr, but we have reports that thread leaks are happening
    with patch("socket.getfqdn", autospec=True, side_effect=Exception), patch(
        "socket.gethostbyaddr", autospec=True, side_effect=Exception
    ):
        yield


@pytest.mark.xfail
def test_when_errors_happen_looking_up_fqdns_threads_should_not_leak(socket_errors):
    before_threads = threading.active_count()
    networkmod.fqdns()
    after_threads = threading.active_count()
    assert (
        before_threads == after_threads
    ), "Difference in thread count means the thread pool is not correctly cleaning up."
