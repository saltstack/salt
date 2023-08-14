import pytest

import salt.utils.process


def transport_ids(value):
    return f"Transport({value})"


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
