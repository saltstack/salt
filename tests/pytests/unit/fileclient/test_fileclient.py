"""
Tests for the salt fileclient
"""

import errno
import logging
import os

import pytest

import salt.utils.files
from salt import fileclient
from tests.support.mock import AsyncMock, MagicMock, Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def mocked_opts(tmp_path):
    fs_root = os.path.join(tmp_path, "fileclient_fs_root")
    cache_root = os.path.join(tmp_path, "fileclient_cache_root")
    return {
        "file_roots": {x: [os.path.join(fs_root, x)] for x in ("base", "dev")},
        "fileserver_backend": ["roots"],
        "cachedir": cache_root,
        "file_client": "local",
    }


@pytest.fixture
def configure_loader_modules(tmp_path, mocked_opts):
    return {fileclient: {"__opts__": mocked_opts}}


@pytest.fixture
def file_client(mocked_opts):
    client = fileclient.Client(mocked_opts)
    try:
        yield client
    finally:
        del client


@pytest.fixture
def client_opts():
    return {
        "extension_modules": "",
        "cachedir": "/__test__",
    }


def _fake_makedir(num=errno.EEXIST):
    def _side_effect(*args, **kwargs):
        raise OSError(num, f"Errno {num}")

    return Mock(side_effect=_side_effect)


class MockReqChannel:
    def factory(self, opts):
        return self

    def close(self):
        return True

    def send(self, load):
        return self


def test_fileclient_context_manager_closes(minion_opts, master_opts):
    """
    ensure fileclient channel closes
    when used with a context manager
    """
    minion_opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": master_opts["ret_port"],
            "master_uri": f"tcp://127.0.0.1:{master_opts['ret_port']}",
            "request_channel_timeout": 1,
            "request_channel_tries": 1,
        }
    )
    mock_reqchannel = MockReqChannel()
    patch_reqchannel = patch.object(
        salt.channel.client, "ReqChannel", return_value=mock_reqchannel
    )
    with patch_reqchannel:
        with fileclient.get_file_client(minion_opts) as client:
            client.master_opts()
            assert not client._closing

        assert client._closing
        assert client.channel.close.called


@pytest.mark.slow_test
def test_fileclient_timeout(minion_opts, master_opts):
    """
    ensure fileclient channel closes
    when used with a context manager
    """
    minion_opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": master_opts["ret_port"],
            "master_uri": f"tcp://127.0.0.1:{master_opts['ret_port']}",
            "request_channel_timeout": 1,
            "request_channel_tries": 1,
        }
    )

    def mock_dumps(*args):
        return b"meh"

    with fileclient.get_file_client(minion_opts) as client:
        # Authenticate must return true
        with patch.object(client.auth, "authenticate", AsyncMock(return_value=True)):
            # Crypticle must return bytes to pass to transport.RequestClient.send
            client.auth._crypticle = Mock()
            client.auth._crypticle.dumps = mock_dumps
            msg = r"^File client timed out after \d{1,4} seconds$"
            with pytest.raises(salt.exceptions.SaltClientError, match=msg):
                client.file_list()


def test_cache_skips_makedirs_on_race_condition(client_opts):
    """
    If cache contains already a directory, do not raise an exception.
    """
    with patch("os.path.isfile", return_value=False):
        for exists in range(2):
            with patch("os.makedirs", _fake_makedir()):
                with fileclient.Client(client_opts)._cache_loc("testfile") as c_ref_itr:
                    assert c_ref_itr == os.sep + os.sep.join(
                        ["__test__", "files", "base", "testfile"]
                    )


def test_cache_raises_exception_on_non_eexist_ioerror(client_opts):
    """
    If makedirs raises other than EEXIST errno, an exception should be raised.
    """
    with patch("os.path.isfile", return_value=False):
        with patch("os.makedirs", _fake_makedir(num=errno.EROFS)):
            with pytest.raises(OSError):
                with fileclient.Client(client_opts)._cache_loc("testfile") as c_ref_itr:
                    assert c_ref_itr == "/__test__/files/base/testfile"


def test_cache_extrn_path_valid(client_opts):
    """
    Tests for extrn_filepath for a given url
    """
    file_name = "http://localhost:8000/test/location/src/dev/usr/file"

    ret = fileclient.Client(client_opts)._extrn_path(file_name, "base")
    assert ":" not in ret
    assert ret == os.path.join("__test__", "extrn_files", "base", ret)


def test_cache_extrn_path_invalid(client_opts):
    """
    Tests for extrn_filepath for a given url
    """
    file_name = "http://localhost:8000/../../../../../usr/bin/bad"

    ret = fileclient.Client(client_opts)._extrn_path(file_name, "base")
    assert ret == "Invalid path"


def test_extrn_path_with_long_filename(client_opts):
    safe_file_name = os.path.split(
        fileclient.Client(client_opts)._extrn_path(
            "https://test.com/" + ("A" * 254), "base"
        )
    )[-1]
    assert safe_file_name == "A" * 254

    oversized_file_name = os.path.split(
        fileclient.Client(client_opts)._extrn_path(
            "https://test.com/" + ("A" * 255), "base"
        )
    )[-1]
    assert len(oversized_file_name) < 256
    assert oversized_file_name != "A" * 255

    oversized_file_with_query_params = os.path.split(
        fileclient.Client(client_opts)._extrn_path(
            "https://test.com/file?" + ("A" * 255), "base"
        )
    )[-1]
    assert len(oversized_file_with_query_params) < 256


def test_file_list_emptydirs(file_client):
    """
    Ensure that the fileclient class won't allow a direct call to file_list_emptydirs()
    """
    with pytest.raises(NotImplementedError):
        file_client.file_list_emptydirs()


def test_get_file(file_client):
    """
    Ensure that the fileclient class won't allow a direct call to get_file()
    """
    with pytest.raises(NotImplementedError):
        file_client.get_file(None)


def test_get_file_client(file_client):
    minion_opts = {}
    minion_opts["file_client"] = "remote"
    with patch("salt.fileclient.RemoteClient", MagicMock(return_value="remote_client")):
        ret = fileclient.get_file_client(minion_opts)
        assert "remote_client" == ret
