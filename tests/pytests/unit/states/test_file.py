import os

import pytest

import salt.modules.file as filemod
import salt.states.file as file
from tests.support.mock import MagicMock, call, create_autospec, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        file: {
            "__opts__": {"test": False},
            "__env__": "base",
        }
    }


@pytest.fixture
def fake_remove():
    fake_remove_mod = create_autospec(filemod.remove)
    with patch.dict(file.__salt__, {"file.remove": fake_remove_mod}):
        yield fake_remove_mod


# TODO: This file.absent test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
@pytest.mark.parametrize("mock_mod", ["os.path.isfile", "os.path.isdir"])
def test_file_absent_should_use_force_mode_for_file_remove(fake_remove, mock_mod):
    expected_path = "/some/abspath/foo"
    with patch(mock_mod, autospec=True, return_value=True):
        file.absent(expected_path)

    fake_remove.assert_called_with(expected_path, force=True)


# TODO: This file.matches test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
def test_file_tidied_for_file_remove(fake_remove):
    patch_is_dir = patch("os.path.isdir", autospec=True, return_value=True)
    patch_os_walk = patch(
        "os.walk",
        autospec=True,
        return_value=[("some root", ("dirs",), ("file1", "file2"))],
    )
    patch_stat = patch("os.stat", autospec=True)
    with patch_os_walk, patch_is_dir, patch_stat as fake_stat:
        fake_stat.return_value.st_atime = 1600356711.1166897
        fake_stat.return_value.st_mode = 33188
        fake_stat.return_value.st_size = 9001  # It's over 9000!

        file.tidied("/some/directory/tree")

    call_root_file1 = f"some root{os.sep}file1"
    call_root_file2 = f"some root{os.sep}file2"
    fake_remove.assert_has_calls([call(call_root_file1), call(call_root_file2)])


# TODO: This file.copy test should be a functional test instead. For now this is probably good enough -W. Werner, 2020-09-15
def test_file_copy_should_use_provided_force_mode_for_file_remove(fake_remove):

    with patch("os.path.lexists", autospec=True, return_value=True), patch(
        "os.path.isfile", autospec=True, return_value=True
    ), patch("os.path.exists", autospec=True, return_value=True), patch.dict(
        file.__opts__, {"user": "somefakeouser"}
    ), patch(
        "salt.states.file._check_user", autospec=True, return_value=False
    ), patch(
        "salt.utils.hashutils.get_hash", autospec=True, return_value=["12345", "54321"]
    ):
        file.copy_("/tmp/foo", source="/tmp/bar", group="fnord", force=True, mode=777)

    fake_remove.assert_called_with("/tmp/foo", force=True)


class TestGetHttpParamsFromSource:
    """Unit tests for salt.states.file._get_http_params_from_source (PR #67153)."""

    def test_none_source_returns_none_and_empty_params(self):
        url, http_params = file._get_http_params_from_source(None)
        assert url is None
        assert http_params == {}

    def test_string_source_passes_through_unchanged(self):
        src = "https://example.com/file.tar.gz"
        url, http_params = file._get_http_params_from_source(src)
        assert url == src
        assert http_params == {}

    def test_list_source_passes_through_unchanged(self):
        src = [
            "https://example.com/file.tar.gz",
            "https://mirror.example.com/file.tar.gz",
        ]
        url, http_params = file._get_http_params_from_source(src)
        assert url == src
        assert http_params == {}

    def test_dict_source_extracts_url_and_headers(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "headers": {"Authorization": "Bearer token"},
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert http_params == {"headers": {"Authorization": "Bearer token"}}

    def test_dict_source_extracts_url_and_all_valid_params(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "headers": {"X-Custom": "value"},
            "params": {"key": "val"},
            "username": "user",
            "password": "pass",
            "auth": ("user", "pass"),
            "backend": "requests",
            "port": 8443,
            "agent": "curl",
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert http_params["headers"] == {"X-Custom": "value"}
        assert http_params["params"] == {"key": "val"}
        assert http_params["username"] == "user"
        assert http_params["password"] == "pass"
        assert http_params["auth"] == ("user", "pass")
        assert http_params["backend"] == "requests"
        assert http_params["port"] == 8443
        assert http_params["agent"] == "curl"

    def test_dict_source_ignores_unknown_keys(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "unknown_key": "should_be_ignored",
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert "unknown_key" not in http_params

    def test_dict_source_cert_as_string(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "cert": "/path/to/cert.pem",
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert http_params["cert"] == "/path/to/cert.pem"

    def test_dict_source_cert_as_dict_with_key(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "cert": {"cert": "/path/to/cert.pem", "key": "/path/to/key.pem"},
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert http_params["cert"] == ["/path/to/cert.pem", "/path/to/key.pem"]

    def test_dict_source_cert_as_dict_without_key(self):
        src = {
            "url": "https://example.com/file.tar.gz",
            "cert": {"cert": "/path/to/cert.pem"},
        }
        url, http_params = file._get_http_params_from_source(src)
        assert url == "https://example.com/file.tar.gz"
        assert http_params["cert"] == "/path/to/cert.pem"

    def test_dict_source_without_url_raises(self):
        src = {"headers": {"X-Custom": "value"}}
        with pytest.raises(KeyError):
            file._get_http_params_from_source(src)


def test_file_recurse_directory_test():
    salt_dunder = {
        "cp.list_master_dirs": MagicMock(return_value=[]),
        "file.source_list": MagicMock(return_value=("salt://does_not_exist", "")),
    }
    with patch.dict(file.__salt__, salt_dunder):
        ret = file.recurse("/tmp/test", "salt://does_not_exist", saltenv="base")
        assert ret == {
            "changes": {},
            "comment": "Recurse failed: none of the specified sources were found",
            "name": "/tmp/test",
            "result": False,
        }
        salt_dunder["cp.list_master_dirs"].assert_called_once_with(
            saltenv="base",
        )
