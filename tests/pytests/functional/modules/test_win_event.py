import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def win_event(modules):
    return modules.win_event


def test_get(win_event):
    events = win_event.get()
    assert events == {}
