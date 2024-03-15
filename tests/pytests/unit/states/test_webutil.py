"""
    :codeauthor: Alexander Pyatkin <asp@thexyz.net>
"""

import pytest

import salt.states.webutil as htpasswd
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {htpasswd: {"__opts__": {"test": False}}}


def test_user_exists_already():
    """
    Test if it returns True when user already exists in htpasswd file
    """

    mock = MagicMock(return_value={"retcode": 0})
    mock_file_exists = MagicMock(return_value={"retcode": 1})

    with patch.dict(
        htpasswd.__salt__, {"file.grep": mock, "file.file_exists": mock_file_exists}
    ):
        ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
        expected = {
            "name": "larry",
            "result": True,
            "comment": "User already known",
            "changes": {},
        }
        assert ret == expected


def test_new_user_success():
    """
    Test if it returns True when new user is added to htpasswd file
    """

    mock_file_exists = MagicMock(return_value={"retcode": 1})
    mock_grep = MagicMock(return_value={"retcode": 1})
    mock_useradd = MagicMock(return_value={"retcode": 0, "stderr": "Success"})

    with patch.dict(
        htpasswd.__salt__,
        {
            "file.grep": mock_grep,
            "file.file_exists": mock_file_exists,
            "webutil.useradd": mock_useradd,
        },
    ):
        ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
        expected = {
            "name": "larry",
            "result": True,
            "comment": "Success",
            "changes": {"larry": True},
        }
        assert ret == expected


def test_new_user_error():
    """
    Test if it returns False when adding user to htpasswd failed
    """

    mock_file_exists = MagicMock(return_value={"retcode": 1})
    mock_grep = MagicMock(return_value={"retcode": 1})
    mock_useradd = MagicMock(return_value={"retcode": 1, "stderr": "Error"})

    with patch.dict(
        htpasswd.__salt__,
        {
            "file.grep": mock_grep,
            "file.file_exists": mock_file_exists,
            "webutil.useradd": mock_useradd,
        },
    ):
        ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
        expected = {
            "name": "larry",
            "result": False,
            "comment": "Error",
            "changes": {},
        }
        assert ret == expected


def test_no_htpasswd_file_and_user_doesnt_exist(tmp_path):
    """
    Test if .htpasswd does not exist, it returns that the user does not
    exist as opposed to erroring out
    """
    htpasswd_file = tmp_path / ".htpasswd"
    assert not htpasswd_file.is_file()

    mock_file_exists = MagicMock(return_value={"retcode": 1})
    mock_grep = MagicMock(return_value={"retcode": 1})
    mock_useradd = MagicMock(return_value={"retcode": 0, "stderr": "Success"})

    with patch.dict(
        htpasswd.__salt__,
        {
            "file.grep": mock_grep,
            "file.file_exists": mock_file_exists,
            "webutil.useradd": mock_useradd,
        },
    ):
        ret = htpasswd.user_exists("larry", "badpass", "/etc/httpd/htpasswd")
        expected = {
            "name": "larry",
            "result": True,
            "comment": "Success",
            "changes": {"larry": True},
        }
        assert ret == expected
