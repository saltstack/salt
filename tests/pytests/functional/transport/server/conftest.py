import salt.utils.process

import pytest

def transport_ids(value):
    return "Transport({})".format(value)


@pytest.fixture(params=("zeromq", "tcp", "ws"), ids=transport_ids)
def transport(request):
    return request.param


@pytest.fixture
def process_manager():
    pm = salt.utils.process.ProcessManager()
    try:
        yield pm
    finally:
        pm.terminate()
