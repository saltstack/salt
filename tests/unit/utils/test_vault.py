"""
Test case for the vault utils module
"""
import json
import logging
import os
from copy import copy

import salt.utils.vault as vault
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import ANY, MagicMock, Mock, mock_open, patch
from tests.support.unit import TestCase


class RequestMock(Mock):
    """
    Request Mock
    """

    def get(self, *args, **kwargs):
        return {}


class TestVaultUtils(LoaderModuleMockMixin, TestCase):
    """
    Test case for the vault utils module
    """

    json_success = {
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
    json_denied = {"errors": ["permission denied"]}
    cache_single = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
    }
    cache_single_namespace = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": "test_namespace",
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
    }
    cache_uses = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 10,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }
    cache_uses_last = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 1,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": False,
    }
    cache_unlimited = {
        "url": "http://127.0.0.1:8200",
        "token": "test",
        "verify": None,
        "namespace": None,
        "uses": 0,
        "lease_duration": 100,
        "issued": 3000,
        "unlimited_use_token": True,
    }
    metadata_v2 = {
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
    cache_secret_meta = {"vault_secret_path_metadata": {"secret/mything": metadata_v2}}

    def setup_loader_modules(self):
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
                    "cachedir": "somepath",
                },
                "__grains__": {"id": "test-minion"},
                "__context__": {},
            }
        }

    def _mock_json_response(self, data, status_code=200, reason=""):
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

    def test_make_request_single_use_token_run_ok(self):
        """
        Given single use token in __context__, function should run successful secret lookup with no other modifications
        """
        mock = self._mock_json_response(self.json_success)
        supplied_context = {"vault_token": copy(self.cache_single)}
        expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
        with patch.dict(vault.__context__, supplied_context):
            with patch("requests.request", mock):
                vault_return = vault.make_request("/secret/my/secret", "key")
                self.assertEqual(vault.__context__, {})
                mock.assert_called_with(
                    "/secret/my/secret",
                    "http://127.0.0.1:8200/key",
                    headers=expected_headers,
                    verify=ANY,
                )
                self.assertEqual(vault_return.json(), self.json_success)

    def test_make_request_single_use_token_run_auth_error(self):
        """
        Given single use token in __context__ and login error, function should request token and re-run
        """
        # Disable logging because simulated http failures are logged as errors
        logging.disable(logging.CRITICAL)
        mock = self._mock_json_response(self.json_denied, status_code=400)
        supplied_context = {"vault_token": copy(self.cache_single)}
        expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
        with patch.dict(vault.__context__, supplied_context):
            with patch("requests.request", mock):
                with patch.object(vault, "del_cache") as mock_del_cache:
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    self.assertEqual(vault.__context__, {})
                    mock.assert_called_with(
                        "/secret/my/secret",
                        "http://127.0.0.1:8200/key",
                        headers=expected_headers,
                        verify=ANY,
                    )
                    self.assertEqual(vault_return.json(), self.json_denied)
                    mock_del_cache.assert_called()
                    self.assertEqual(mock.call_count, 2)
        logging.disable(logging.NOTSET)

    def test_multi_use_token_successful_run(self):
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
        mock = self._mock_json_response(self.json_success)
        expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
        with patch.object(vault, "get_cache") as mock_get_cache:
            mock_get_cache.return_value = copy(self.cache_uses)
            with patch("requests.request", mock):
                with patch.object(vault, "del_cache") as mock_del_cache:
                    with patch.object(vault, "write_cache") as mock_write_cache:
                        vault_return = vault.make_request("/secret/my/secret", "key")
                        mock.assert_called_with(
                            "/secret/my/secret",
                            "http://127.0.0.1:8200/key",
                            headers=expected_headers,
                            verify=ANY,
                        )
                        mock_write_cache.assert_called_with(expected_cache_write)
                        self.assertEqual(vault_return.json(), self.json_success)
                        self.assertEqual(mock.call_count, 1)

    def test_multi_use_token_last_use(self):
        """
        Given last use of multi-use token, function should succeed and flush token cache
        """
        mock = self._mock_json_response(self.json_success)
        expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
        with patch.object(vault, "get_cache") as mock_get_cache:
            mock_get_cache.return_value = self.cache_uses_last
            with patch("requests.request", mock):
                with patch.object(vault, "del_cache") as mock_del_cache:
                    with patch.object(vault, "write_cache") as mock_write_cache:
                        vault_return = vault.make_request("/secret/my/secret", "key")
                        mock.assert_called_with(
                            "/secret/my/secret",
                            "http://127.0.0.1:8200/key",
                            headers=expected_headers,
                            verify=ANY,
                        )
                        mock_del_cache.assert_called()
                        self.assertEqual(vault_return.json(), self.json_success)
                        self.assertEqual(mock.call_count, 1)

    def test_unlimited_use_token_no_decrement(self):
        """
        Given unlimited-use token, function should succeed not del cache or decrement
        """
        mock = self._mock_json_response(self.json_success)
        expected_headers = {"X-Vault-Token": "test", "Content-Type": "application/json"}
        with patch.object(vault, "get_cache") as mock_get_cache:
            mock_get_cache.return_value = self.cache_unlimited
            with patch("requests.request", mock):
                with patch.object(vault, "del_cache") as mock_del_cache:
                    with patch.object(vault, "write_cache") as mock_write_cache:
                        vault_return = vault.make_request("/secret/my/secret", "key")
                        mock.assert_called_with(
                            "/secret/my/secret",
                            "http://127.0.0.1:8200/key",
                            headers=expected_headers,
                            verify=ANY,
                        )
                        assert (
                            not mock_del_cache.called
                        ), "del cache should not be called for unlimited use token"
                        assert (
                            not mock_write_cache.called
                        ), "write cache should not be called for unlimited use token"
                        self.assertEqual(vault_return.json(), self.json_success)
                        self.assertEqual(mock.call_count, 1)

    def test_get_cache_standard(self):
        """
        test standard first run of no cache file. Should generate new connection and write cache
        """
        with patch.object(vault, "_read_cache_file") as mock_read_cache:
            mock_read_cache.return_value = {}
            with patch.object(
                vault, "get_vault_connection"
            ) as mock_get_vault_connection:
                mock_get_vault_connection.return_value = copy(self.cache_single)
                with patch.object(vault, "write_cache") as mock_write_cache:
                    cache_result = vault.get_cache()
                    mock_write_cache.assert_called_with(copy(self.cache_single))

    def test_get_cache_existing_cache_valid(self):
        """
        test standard valid cache file
        """
        with patch("time.time", return_value=1234):
            with patch.object(vault, "_read_cache_file") as mock_read_cache:
                mock_read_cache.return_value = self.cache_uses
                with patch.object(vault, "write_cache") as mock_write_cache:
                    with patch.object(vault, "del_cache") as mock_del_cache:
                        cache_result = vault.get_cache()
                        assert not mock_write_cache.called
                        assert not mock_del_cache.called
                        self.assertEqual(cache_result, self.cache_uses)

    def test_get_cache_existing_cache_old(self):
        """
        test old cache file
        """
        with patch("time.time", return_value=3101):
            with patch.object(
                vault, "get_vault_connection"
            ) as mock_get_vault_connection:
                mock_get_vault_connection.return_value = self.cache_uses
                with patch.object(vault, "_read_cache_file") as mock_read_cache:
                    mock_read_cache.return_value = self.cache_uses
                    with patch.object(vault, "write_cache") as mock_write_cache:
                        with patch.object(vault, "del_cache") as mock_del_cache:
                            cache_result = vault.get_cache()
                            assert mock_del_cache.called
                            assert mock_write_cache.called
                            self.assertEqual(cache_result, self.cache_uses)

    def test_write_cache_standard(self):
        """
        Test write cache with standard single use token
        """
        function_response = vault.write_cache(copy(self.cache_single))
        self.assertEqual(vault.__context__["vault_token"], copy(self.cache_single))
        self.assertTrue(function_response)

    def test_write_cache_multi_use_token(self):
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
        with patch("salt.utils.files.fpopen", mock_open()) as mock_fpopen:
            function_response = vault.write_cache(self.cache_uses)
            assert mock_fpopen.call_count == 1
            self.assertListEqual(
                list(mock_fpopen.filehandles),
                [os.path.join("somepath", "salt_vault_token")],
            )
            opens = mock_fpopen.filehandles[
                os.path.join("somepath", "salt_vault_token")
            ]
            write_calls_output = json.loads(opens[0].write_calls[0])
            self.assertDictEqual(write_calls_output, expected_write)
            self.assertTrue(function_response)

    def test_write_cache_unlimited_token(self):
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

        with patch("salt.utils.files.fpopen", mock_open()) as mock_fpopen:
            function_response = vault.write_cache(write_data)
            assert mock_fpopen.call_count == 1
            self.assertListEqual(
                list(mock_fpopen.filehandles),
                [os.path.join("somepath", "salt_vault_token")],
            )
            opens = mock_fpopen.filehandles[
                os.path.join("somepath", "salt_vault_token")
            ]
            write_calls_output = json.loads(opens[0].write_calls[0])
            self.assertEqual(write_calls_output, expected_write)
            self.assertTrue(function_response)

    def test_path_is_v2(self):
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
            mock_get_metadata.return_value = self.metadata_v2
            function_return = vault.is_v2("secret/mything")
            self.assertEqual(function_return, expected_return)

    def test_request_with_namespace(self):
        """
        Test request with namespace configured
        """
        mock = self._mock_json_response(self.json_success)
        expected_headers = {
            "X-Vault-Token": "test",
            "X-Vault-Namespace": "test_namespace",
            "Content-Type": "application/json",
        }
        supplied_config = {"namespace": "test_namespace"}
        supplied_context = {"vault_token": copy(self.cache_single_namespace)}
        with patch.dict(vault.__context__, supplied_context):
            with patch.dict(vault.__opts__["vault"], supplied_config):
                with patch("requests.request", mock):
                    vault_return = vault.make_request("/secret/my/secret", "key")
                    mock.assert_called_with(
                        "/secret/my/secret",
                        "http://127.0.0.1:8200/key",
                        headers=expected_headers,
                        verify=ANY,
                    )
                    self.assertEqual(vault_return.json(), self.json_success)

    def test_get_secret_path_metadata_no_cache(self):
        """
        test with no cache file
        """
        make_request_response = {
            "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
            "lease_id": "",
            "renewable": False,
            "lease_duration": 0,
            "data": self.metadata_v2,
            "wrap_info": None,
            "warnings": None,
            "auth": None,
        }
        cache_object = copy(self.cache_uses)
        expected_cache_object = copy(self.cache_uses)
        expected_cache_object.update(copy(self.cache_secret_meta))
        secret_path = "secret/mything"
        mock = self._mock_json_response(make_request_response)
        with patch.object(vault, "_read_cache_file") as mock_read_cache:
            mock_read_cache.return_value = cache_object
            with patch.object(vault, "write_cache") as mock_write_cache:
                with patch("salt.utils.vault.make_request", mock):
                    function_result = vault._get_secret_path_metadata(secret_path)
                    self.assertEqual(function_result, self.metadata_v2)
                    mock_write_cache.assert_called_with(cache_object)
                    self.assertEqual(cache_object, expected_cache_object)
