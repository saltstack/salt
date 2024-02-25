import json
import logging
import threading
from copy import copy

import pytest

import salt.utils.files
import salt.utils.vault as vault
from tests.support.mock import ANY, MagicMock, Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def tmp_cache(tmp_path):
    cachedir = tmp_path / "cachedir"
    cachedir.mkdir()
    return cachedir


@pytest.fixture
def configure_loader_modules(tmp_cache):
    return {
        vault: {
            "__opts__": {
                "vault": {
                    "url": "http://127.0.0.1",
                    "auth": {
                        "token": "test",
                        "method": "token",
                        "uses": 15,
                        "ttl": 500,
                    },
                },
                "file_client": "local",
                "cachedir": str(tmp_cache),
            },
            "__grains__": {"id": "test-minion"},
            "__context__": {},
        }
    }


@pytest.fixture
def json_success():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "data": {"something": "myvalue"},
            "metadata": {
                "created_time": "2020-05-02T07:26:12.180848003Z",
                "deletion_time": "",
                "destroyed": False,
                "version": 1,
            },
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def json_denied():
    return {"errors": ["permission denied"]}


@pytest.fixture
def cache_single():
    return {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
    }


@pytest.fixture
def cache_single_namespace():
    return {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": "test_namespace",
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
    }


@pytest.fixture
def cache_uses():
    return {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 10,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }


@pytest.fixture
def cache_uses_last():
    return {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }


@pytest.fixture
def cache_unlimited():
    return {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 0,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": True,
    }


@pytest.fixture
def metadata_v2():
    return {
        "accessor": "kv_f8731f1b",
        "config": {
            "default_lease_ttl": 0,
            "force_no_cache": False,
            "max_lease_ttl": 0,
        },
        "description": "key/value secret storage",
        "external_entropy_access": False,
        "local": False,
        "options": {"version": "2"},
        "path": "secret/",
        "seal_wrap": False,
        "type": "kv",
        "uuid": "1d9431ac-060a-9b63-4572-3ca7ffd78347",
    }


@pytest.fixture
def cache_secret_meta(metadata_v2):
    return {"vault_secret_path_metadata": {"secret/mything": metadata_v2}}


def _mock_json_response(data, status_code=200, reason=""):
    """
    Mock helper for http response
    """
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    response.status_code = status_code
    response.reason = reason
    if status_code == 200:
        response.ok = True
    else:
        response.ok = False
    return Mock(return_value=response)


def test_write_cache_multi_use_token(cache_uses, tmp_cache):
    """
    Test write cache with multi-use token
    """
    expected_write = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 10,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }
    function_response = vault.write_cache(cache_uses)
    assert function_response is True
    with salt.utils.files.fopen(str(tmp_cache / "salt_vault_token"), "r") as fp:
        token_data = json.loads(fp.read())
    assert token_data == expected_write


def test_write_cache_unlimited_token(cache_uses, tmp_cache):
    """
    Test write cache with unlimited use token
    """
    write_data = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 0,
        "lease_duration": 100,
        "issued": 3000,
    }
    expected_write = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 0,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": True,
    }
    function_response = vault.write_cache(write_data)
    with salt.utils.files.fopen(str(tmp_cache / "salt_vault_token"), "r") as fp:
        token_data = json.loads(fp.read())
    assert token_data == expected_write


def test_write_cache_issue_59361(cache_uses, tmp_cache):
    """
    Test race condition fix (Issue 59361)
    """
    evt = threading.Event()

    def target(evt, cache_uses):
        evt.wait()
        function_response = vault.write_cache(cache_uses)

    cached_token = {
        "url": "http://127.0.0.1:8200",
        "token": "testwithmuchmuchlongertoken",
        "verify": None,
        "namespace": None,
        "uses": 10,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }
    expected_write = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 10,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }

    thread1 = threading.Thread(
        target=target,
        args=(
            evt,
            cached_token,
        ),
    )
    thread1.start()
    thread2 = threading.Thread(
        target=target,
        args=(
            evt,
            expected_write,
        ),
    )
    thread2.start()
    evt.set()
    thread1.join()
    thread2.join()

    with salt.utils.files.fopen(str(tmp_cache / "salt_vault_token"), "r") as fp:
        try:
            token_data = json.loads(fp.read())
        except json.decoder.JSONDecodeError:
            assert False, "Cache file data corrupted"


def test_make_request_single_use_token_run_ok(json_success, cache_single):
    """
    Given single use token in __context__, function should run successful secret lookup with no other modifications
    """
    mock = _mock_json_response(json_success)
    supplied_context = {"vault_token": copy(cache_single)}
    expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
    with patch.dict(vault.__context__, supplied_context):
        with patch("requests.request", mock):
            vault_return = vault.make_request("/secret/my/secret", "key")
            assert vault.__context__ == {}
            mock.assert_called_with(
                "/secret/my/secret",
                "http://127.0.0.1:8200/key",
                headers=expected_headers,
                verify=ANY,
                timeout=ANY,
            )
            assert vault_return.json() == json_success


def test_make_request_single_use_token_run_auth_error(json_denied, cache_single):
    """
    Given single use token in __context__ and login error, function should request token and re-run
    """
    # Disable logging because simulated http failures are logged as errors
    logging.disable(logging.CRITICAL)
    mock = _mock_json_response(json_denied, status_code=400)
    supplied_context = {"vault_token": cache_single}
    expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
    with patch.dict(vault.__context__, supplied_context):
        with patch("requests.request", mock):
            with patch.object(vault, "del_cache") as mock_del_cache:
                vault_return = vault.make_request("/secret/my/secret", "key")
                assert vault.__context__ == {}
                mock.assert_called_with(
                    "/secret/my/secret",
                    "http://127.0.0.1:8200/key",
                    headers=expected_headers,
                    verify=ANY,
                    timeout=ANY,
                )
                assert vault_return.json() == json_denied
                mock_del_cache.assert_called()
                assert mock.call_count == 2
    logging.disable(logging.NOTSET)


def test_multi_use_token_successful_run(json_success, cache_uses):
    """
    Given multi-use token, function should get secret and decrement token
    """
    expected_cache_write = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 9,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }
    mock = _mock_json_response(json_success)
    expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
    with patch.object(vault, "get_cache") as mock_get_cache:
        mock_get_cache.return_value = copy(cache_uses)
        with patch("requests.request", mock):
            with patch.object(vault, "del_cache") as mock_del_cache:
                with patch.object(vault, "write_cache") as mock_write_cache:
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    mock.assert_called_with(
                        "/secret/my/secret",
                        "http://127.0.0.1:8200/key",
                        headers=expected_headers,
                        verify=ANY,
                        timeout=ANY,
                    )
                    mock_write_cache.assert_called_with(expected_cache_write)
                    assert vault_return.json() == json_success
                    assert mock.call_count == 1


def test_multi_use_token_last_use(json_success, cache_uses_last):
    """
    Given last use of multi-use token, function should succeed and flush token cache
    """
    mock = _mock_json_response(json_success)
    expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
    with patch.object(vault, "get_cache") as mock_get_cache:
        mock_get_cache.return_value = cache_uses_last
        with patch("requests.request", mock):
            with patch.object(vault, "del_cache") as mock_del_cache:
                with patch.object(vault, "write_cache") as mock_write_cache:
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    mock.assert_called_with(
                        "/secret/my/secret",
                        "http://127.0.0.1:8200/key",
                        headers=expected_headers,
                        verify=ANY,
                        timeout=ANY,
                    )
                    mock_del_cache.assert_called()
                    assert vault_return.json() == json_success
                    assert mock.call_count == 1


def test_unlimited_use_token_no_decrement(json_success, cache_unlimited):
    """
    Given unlimited-use token, function should succeed not del cache or decrement
    """
    mock = _mock_json_response(json_success)
    expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
    with patch.object(vault, "get_cache") as mock_get_cache:
        mock_get_cache.return_value = cache_unlimited
        with patch("requests.request", mock):
            with patch.object(vault, "del_cache") as mock_del_cache:
                with patch.object(vault, "write_cache") as mock_write_cache:
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    mock.assert_called_with(
                        "/secret/my/secret",
                        "http://127.0.0.1:8200/key",
                        headers=expected_headers,
                        verify=ANY,
                        timeout=ANY,
                    )
                    assert (
                        not mock_del_cache.called
                    ), "del cache should not be called for unlimited use token"
                    assert (
                        not mock_write_cache.called
                    ), "write cache should not be called for unlimited use token"
                    assert vault_return.json() == json_success
                    assert mock.call_count == 1


def test_get_cache_standard(cache_single):
    """
    test standard first run of no cache file. Should generate new connection and write cache
    """
    with patch.object(vault, "_read_cache_file") as mock_read_cache:
        mock_read_cache.return_value = {}
        with patch.object(vault, "get_vault_connection") as mock_get_vault_connection:
            mock_get_vault_connection.return_value = copy(cache_single)
            with patch.object(vault, "write_cache") as mock_write_cache:
                cache_result = vault.get_cache()
                mock_write_cache.assert_called_with(copy(cache_single))


def test_get_cache_existing_cache_valid(cache_uses):
    """
    test standard valid cache file
    """
    with patch("time.time", return_value=1234):
        with patch.object(vault, "_read_cache_file") as mock_read_cache:
            mock_read_cache.return_value = cache_uses
            with patch.object(vault, "write_cache") as mock_write_cache:
                with patch.object(vault, "del_cache") as mock_del_cache:
                    cache_result = vault.get_cache()
                    assert not mock_write_cache.called
                    assert not mock_del_cache.called
                    assert cache_result == cache_uses


def test_get_cache_existing_cache_old(cache_uses):
    """
    test old cache file
    """
    with patch("time.time", return_value=3101):
        with patch.object(vault, "get_vault_connection") as mock_get_vault_connection:
            mock_get_vault_connection.return_value = cache_uses
            with patch.object(vault, "_read_cache_file") as mock_read_cache:
                mock_read_cache.return_value = cache_uses
                with patch.object(vault, "write_cache") as mock_write_cache:
                    with patch.object(vault, "del_cache") as mock_del_cache:
                        cache_result = vault.get_cache()
                        assert mock_del_cache.called
                        assert mock_write_cache.called
                        assert cache_result == cache_uses


def test_write_cache_standard(cache_single):
    """
    Test write cache with standard single use token
    """
    function_response = vault.write_cache(copy(cache_single))
    assert vault.__context__["vault_token"] == copy(cache_single)
    assert function_response is True


def test_path_is_v2(metadata_v2):
    """
    Validated v2 path is detected as vault kv v2
    """
    expected_return = {
        "v2": True,
        "data": "secret/data/mything",
        "metadata": "secret/metadata/mything",
        "delete": "secret/mything",
        "type": "kv",
        "destroy": "secret/destroy/mything",
    }
    with patch.object(vault, "_get_secret_path_metadata") as mock_get_metadata:
        mock_get_metadata.return_value = metadata_v2
        function_return = vault.is_v2("secret/mything")
        assert function_return == expected_return


def test_request_with_namespace(json_success, cache_single_namespace):
    """
    Test request with namespace configured
    """
    mock = _mock_json_response(json_success)
    expected_headers = {
        "X-Vault-Token": "test",
        "X-Vault-Namespace": "test_namespace",
        "Content-Type": "application/json",
    }
    supplied_config = {"namespace": "test_namespace"}
    supplied_context = {"vault_token": copy(cache_single_namespace)}
    with patch.dict(vault.__context__, supplied_context):
        with patch.dict(vault.__opts__["vault"], supplied_config):
            with patch("requests.request", mock):
                vault_return = vault.make_request("/secret/my/secret", "key")
                mock.assert_called_with(
                    "/secret/my/secret",
                    "http://127.0.0.1:8200/key",
                    headers=expected_headers,
                    verify=ANY,
                    timeout=ANY,
                )
                assert vault_return.json() == json_success


def test_get_secret_path_metadata_no_cache(metadata_v2, cache_uses, cache_secret_meta):
    """
    test with no cache file
    """
    make_request_response = {
        "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": metadata_v2,
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }
    cache_object = copy(cache_uses)
    expected_cache_object = copy(cache_uses)
    expected_cache_object.update(copy(cache_secret_meta))
    secret_path = "secret/mything"
    mock = _mock_json_response(make_request_response)
    with patch.object(vault, "_read_cache_file") as mock_read_cache:
        mock_read_cache.return_value = cache_object
        with patch.object(vault, "write_cache") as mock_write_cache:
            with patch("salt.utils.vault.make_request", mock):
                function_result = vault._get_secret_path_metadata(secret_path)
                assert function_result == metadata_v2
                mock_write_cache.assert_called_with(cache_object)
                assert cache_object == expected_cache_object


def test_expand_pattern_lists():
    """
    Ensure expand_pattern_lists works as intended:
    - Expand list-valued patterns
    - Do not change non-list-valued tokens
    """
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": ["single-dict:{minion}"],
        "single-list:{grains[roles]}": ["single-list:web", "single-list:database"],
        "multiple-lists:{grains[roles]}+{grains[aux]}": [
            "multiple-lists:web+foo",
            "multiple-lists:web+bar",
            "multiple-lists:database+foo",
            "multiple-lists:database+bar",
        ],
        "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}": [
            "single-list-with-dicts:{grains[id]}+web+{grains[id]}",
            "single-list-with-dicts:{grains[id]}+database+{grains[id]}",
        ],
        "deeply-nested-list:{grains[deep][foo][bar][baz]}": [
            "deeply-nested-list:hello",
            "deeply-nested-list:world",
        ],
    }

    pattern_vars = {
        "id": "test-minion",
        "roles": ["web", "database"],
        "aux": ["foo", "bar"],
        "deep": {"foo": {"bar": {"baz": ["hello", "world"]}}},
    }

    mappings = {"minion": "test-minion", "grains": pattern_vars}
    for case, correct_output in cases.items():
        output = vault.expand_pattern_lists(case, **mappings)
        assert output == correct_output


@pytest.mark.parametrize(
    "conf_location,called",
    [("local", False), ("master", True), (None, False), ("doesnotexist", False)],
)
def test_get_vault_connection_config_location(tmp_path, conf_location, called, caplog):
    """
    test the get_vault_connection function when
    config_location is set in opts
    """
    token_url = {
        "url": "http://127.0.0.1",
        "namespace": None,
        "token": "test",
        "verify": None,
        "issued": 1666100373,
        "ttl": 3600,
    }

    opts = {"config_location": conf_location, "pki_dir": tmp_path / "pki"}
    with patch.object(vault, "_get_token_and_url_from_master") as patch_token:
        patch_token.return_vaule = token_url
        with patch.dict(vault.__opts__["vault"], opts):
            vault.get_vault_connection()

    if called:
        patch_token.assert_called()
    else:
        patch_token.assert_not_called()
    if conf_location == "doesnotexist":
        assert "config_location must be either local or master" in caplog.text


def test_del_cache(tmp_cache):
    token_file = tmp_cache / "salt_vault_token"
    token_file.touch()
    with patch.dict(vault.__context__, {"vault_token": "fake_token"}):
        vault.del_cache()
        assert "vault_token" not in vault.__context__
    assert not token_file.exists()
