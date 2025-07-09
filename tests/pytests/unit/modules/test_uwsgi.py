"""
    Test cases for salt.modules.uswgi
"""

import pytest

import salt.modules.uwsgi as uwsgi
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    with patch("salt.utils.path.which", Mock(return_value="/usr/bin/uwsgi")):
        return {uwsgi: {}}


def test_uwsgi_stats():
    socket = "127.0.0.1:5050"
    mock = MagicMock(return_value='{"a": 1, "b": 2}')
    with patch.dict(uwsgi.__salt__, {"cmd.run": mock}):
        result = uwsgi.stats(socket)
        mock.assert_called_once_with(
            ["uwsgi", "--connect-and-read", f"{socket}"],
            python_shell=False,
        )
        assert result == {"a": 1, "b": 2}
