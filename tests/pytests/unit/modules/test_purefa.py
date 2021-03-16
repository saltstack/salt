import pytest
import salt.modules.purefa as purefa
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {purefa: {"_get_host": create_autospec(purefa._get_host, return_value=None)}}


@pytest.fixture
def fake_set_host():
    fake_set_host = MagicMock()
    with patch("salt.modules.purefa._get_system", autospec=True) as fake_sys:
        fake_sys.return_value.set_host = fake_set_host
        yield fake_set_host


@pytest.mark.parametrize(
    "nqn", [None, "", [], ()],
)
def test_when_nqn_is_not_anything_set_host_should_not_have_addnqnlist_called(
    nqn, fake_set_host
):
    purefa.host_create("fnord", nqn=nqn)

    for call in fake_set_host.mock_calls:
        assert "addnqnlist" not in call.kwargs
