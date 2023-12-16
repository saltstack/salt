import pytest
import requests.models

import salt.utils.vault as vault
import salt.utils.vault.cache as vcache
import salt.utils.vault.client as vclient
import salt.utils.vault.kv as vkv
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def path():
    return "secret/some/path"


@pytest.fixture
def paths():
    return {
        "data": "secret/data/some/path",
        "metadata": "secret/metadata/some/path",
        "delete": "secret/data/some/path",
        "delete_versions": "secret/delete/some/path",
        "destroy": "secret/destroy/some/path",
    }


@pytest.fixture
def kvv1_meta_response():
    return {
        "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "accessor": "kv_f8731f1b",
            "config": {
                "default_lease_ttl": 0,
                "force_no_cache": False,
                "max_lease_ttl": 0,
            },
            "description": "key/value secret storage",
            "external_entropy_access": False,
            "local": False,
            "options": None,
            "path": "secret/",
            "seal_wrap": False,
            "type": "kv",
            "uuid": "1d9431ac-060a-9b63-4572-3ca7ffd78347",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv2_meta_response():
    return {
        "request_id": "b82f2df7-a9b6-920c-0ed2-a3463b996f9e",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "accessor": "kv_f8731f1b",
            "config": {
                "default_lease_ttl": 0,
                "force_no_cache": False,
                "max_lease_ttl": 0,
            },
            "description": "key/value secret storage",
            "external_entropy_access": False,
            "local": False,
            "options": {
                "version": "2",
            },
            "path": "secret/",
            "seal_wrap": False,
            "type": "kv",
            "uuid": "1d9431ac-060a-9b63-4572-3ca7ffd78347",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv1_info():
    return {
        "v2": False,
        "data": "secret/some/path",
        "metadata": "secret/some/path",
        "delete": "secret/some/path",
        "type": "kv",
    }


@pytest.fixture
def kvv2_info():
    return {
        "v2": True,
        "data": "secret/data/some/path",
        "metadata": "secret/metadata/some/path",
        "delete": "secret/data/some/path",
        "delete_versions": "secret/delete/some/path",
        "destroy": "secret/destroy/some/path",
        "type": "kv",
    }


@pytest.fixture
def no_kv_info():
    return {
        "v2": False,
        "data": "secret/some/path",
        "metadata": "secret/some/path",
        "delete": "secret/some/path",
        "type": None,
    }


@pytest.fixture
def kvv1_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "foo": "bar",
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def kvv2_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "data": {"foo": "bar"},
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
def kv_list_response():
    return {
        "request_id": "35df4df1-c3d8-b270-0682-ddb0160c7450",
        "lease_id": "",
        "renewable": False,
        "lease_duration": 0,
        "data": {
            "keys": ["foo"],
        },
        "wrap_info": None,
        "warnings": None,
        "auth": None,
    }


@pytest.fixture
def metadata_nocache():
    cache = Mock(spec=vcache.VaultCache)
    cache.get.return_value = None
    return cache


@pytest.fixture(params=["v1", "v2"])
def kv_meta(request, metadata_nocache):
    client = Mock(spec=vclient.AuthenticatedVaultClient)
    if request.param == "invalid":
        res = {"wrap_info": {}}
    else:
        res = request.getfixturevalue(f"kv{request.param}_meta_response")
    client.get.return_value = res
    return vkv.VaultKV(client, metadata_nocache)


@pytest.fixture(params=["v1", "v2"])
def kv_meta_cached(request):
    cache = Mock(spec=vcache.VaultCache)
    client = Mock(spec=vclient.AuthenticatedVaultClient)
    kv_meta_response = request.getfixturevalue(f"kv{request.param}_meta_response")
    client.get.return_value = kv_meta_response
    cache.get.return_value = {"secret/some/path": kv_meta_response["data"]}
    return vkv.VaultKV(client, cache)


@pytest.fixture
def kvv1(kvv1_info, kvv1_response, metadata_nocache, kv_list_response):
    client = Mock(spec=vclient.AuthenticatedVaultClient)
    client.get.return_value = kvv1_response
    client.post.return_value = True
    client.patch.side_effect = vclient.VaultPermissionDeniedError
    client.list.return_value = kv_list_response
    client.delete.return_value = True
    with patch("salt.utils.vault.kv.VaultKV.is_v2", Mock(return_value=kvv1_info)):
        yield vkv.VaultKV(client, metadata_nocache)


@pytest.fixture
def kvv2(kvv2_info, kvv2_response, metadata_nocache, kv_list_response):
    client = Mock(spec=vclient.AuthenticatedVaultClient)
    client.get.return_value = kvv2_response
    client.post.return_value = True
    client.patch.return_value = True
    client.list.return_value = kv_list_response
    client.delete.return_value = True
    with patch("salt.utils.vault.kv.VaultKV.is_v2", Mock(return_value=kvv2_info)):
        yield vkv.VaultKV(client, metadata_nocache)


@pytest.mark.parametrize(
    "wrapper,param,result",
    [
        ("read_kv", None, {"foo": "bar"}),
        ("write_kv", {"foo": "bar"}, True),
        ("patch_kv", {"foo": "bar"}, True),
        ("delete_kv", None, True),
        ("destroy_kv", [0], True),
        ("list_kv", None, ["foo"]),
    ],
)
@pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
@pytest.mark.parametrize(
    "clear_unauthd,token_valid", [(False, False), (True, False), (True, True)]
)
def test_kv_wrapper_handles_perm_exceptions(
    wrapper, param, result, test_remote_config, clear_unauthd, token_valid
):
    """
    Test that *_kv wrappers retry with a new client if
      a) the current configuration might be invalid
      b) the current token might not have all policies and
         `cache:clear_on_unauthorized` is True
    """
    func = getattr(vault, wrapper)
    exc = vault.VaultPermissionDeniedError
    args = ["secret/some/path"]
    if param:
        args.append(param)
    args += [{}, {}]
    test_remote_config["cache"]["clear_on_unauthorized"] = clear_unauthd
    with patch("salt.utils.vault.get_kv", autospec=True) as getkv:
        with patch("salt.utils.vault.clear_cache", autospec=True) as cache:
            kv = Mock(spec=vkv.VaultKV)
            kv.client = Mock(spec=vclient.AuthenticatedVaultClient)
            kv.client.token_valid.return_value = token_valid
            getattr(kv, wrapper.rstrip("_kv")).side_effect = (exc, result)
            getkv.side_effect = ((kv, test_remote_config), kv)
            res = func(*args)
            assert res == result
            cache.assert_called_once()


@pytest.mark.parametrize(
    "wrapper,param",
    [
        ("read_kv", None),
        ("write_kv", {"foo": "bar"}),
        ("patch_kv", {"foo": "bar"}),
        ("delete_kv", None),
        ("destroy_kv", [0]),
        ("list_kv", None),
    ],
)
@pytest.mark.parametrize("test_remote_config", ["token"], indirect=True)
def test_kv_wrapper_raises_perm_exceptions_when_configured(
    wrapper, param, test_remote_config
):
    """
    Test that *_kv wrappers do not retry with a new client when `cache:clear_on_unauthorized` is False.
    """
    func = getattr(vault, wrapper)
    exc = vault.VaultPermissionDeniedError
    args = ["secret/some/path"]
    if param:
        args.append(param)
    args += [{}, {}]
    test_remote_config["cache"]["clear_on_unauthorized"] = False
    with patch("salt.utils.vault.get_kv", autospec=True) as getkv:
        with patch("salt.utils.vault.clear_cache", autospec=True):
            kv = Mock(spec=vkv.VaultKV)
            kv.client = Mock(spec=vclient.AuthenticatedVaultClient)
            kv.client.token_valid.return_value = True
            getattr(kv, wrapper.rstrip("_kv")).side_effect = exc
            getkv.return_value = (kv, test_remote_config)
            with pytest.raises(exc):
                func(*args)


@pytest.mark.parametrize(
    "kv_meta,expected",
    [
        (
            "v1",
            "kvv1_info",
        ),
        (
            "v2",
            "kvv2_info",
        ),
        (
            "invalid",
            "no_kv_info",
        ),
    ],
    indirect=["kv_meta"],
)
def test_vault_kv_is_v2_no_cache(kv_meta, expected, request):
    """
    Ensure path metadata is requested as expected and cached
    if the lookup succeeds
    """
    expected_val = request.getfixturevalue(expected)
    res = kv_meta.is_v2("secret/some/path")
    kv_meta.metadata_cache.get.assert_called_once()
    kv_meta.client.get.assert_called_once_with(
        "sys/internal/ui/mounts/secret/some/path"
    )
    if expected != "no_kv_info":
        kv_meta.metadata_cache.store.assert_called_once()
    assert res == expected_val


@pytest.mark.parametrize(
    "kv_meta_cached,expected",
    [
        (
            "v1",
            "kvv1_info",
        ),
        (
            "v2",
            "kvv2_info",
        ),
    ],
    indirect=["kv_meta_cached"],
)
def test_vault_kv_is_v2_cached(kv_meta_cached, expected, request):
    """
    Ensure cache is respected for path metadata
    """
    expected = request.getfixturevalue(expected)
    res = kv_meta_cached.is_v2("secret/some/path")
    kv_meta_cached.metadata_cache.get.assert_called_once()
    kv_meta_cached.metadata_cache.store.assert_not_called()
    kv_meta_cached.client.assert_not_called()
    assert res == expected


class TestKVV1:
    path = "secret/some/path"

    @pytest.mark.parametrize("include_metadata", [False, True])
    def test_vault_kv_read(self, kvv1, include_metadata, path):
        """
        Ensure that VaultKV.read works for KV v1 and does not fail if
        metadata is requested, which is invalid for KV v1.
        """
        res = kvv1.read(path, include_metadata=include_metadata)
        kvv1.client.get.assert_called_once_with(path)
        assert res == {"foo": "bar"}

    def test_vault_kv_write(self, kvv1, path):
        """
        Ensure that VaultKV.write works for KV v1.
        """
        data = {"bar": "baz"}
        kvv1.write(path, data)
        kvv1.client.post.assert_called_once_with(path, payload=data)

    @pytest.mark.parametrize(
        "existing,data,expected",
        [
            ({"foo": "bar"}, {"bar": "baz"}, {"foo": "bar", "bar": "baz"}),
            ({"foo": "bar"}, {"foo": None}, {}),
            (
                {"foo": "bar"},
                {"foo2": {"bar": {"baz": True}}},
                {"foo": "bar", "foo2": {"bar": {"baz": True}}},
            ),
            (
                {"foo": {"bar": {"baz": True}}},
                {"foo": {"bar": {"baz": None}}},
                {"foo": {"bar": {}}},
            ),
        ],
    )
    def test_vault_kv_patch(self, kvv1, path, existing, data, expected):
        """
        Ensure that VaultKV.patch works for KV v1.
        This also tests the internal JSON merge patch implementation.
        """
        kvv1.client.get.return_value = {"data": existing}
        kvv1.patch(path, data)
        kvv1.client.post.assert_called_once_with(
            path,
            payload=expected,
        )

    def test_vault_kv_delete(self, kvv1, path):
        """
        Ensure that VaultKV.delete works for KV v1.
        """
        kvv1.delete(path)
        kvv1.client.request.assert_called_once_with("DELETE", path, payload=None)

    def test_vault_kv_delete_versions(self, kvv1, path):
        """
        Ensure that VaultKV.delete with versions raises an exception for KV v1.
        """
        with pytest.raises(
            vault.VaultInvocationError, match="Versioning support requires kv-v2.*"
        ):
            kvv1.delete(path, versions=[1, 2, 3, 4])

    def test_vault_kv_destroy(self, kvv1, path):
        """
        Ensure that VaultKV.destroy raises an exception for KV v1.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.destroy(path, [1, 2, 3, 4])

    def test_vault_kv_nuke(self, kvv1, path):
        """
        Ensure that VaultKV.nuke raises an exception for KV v1.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.nuke(path)

    def test_vault_kv_list(self, kvv1, path):
        """
        Ensure that VaultKV.list works for KV v1 and only returns keys.
        """
        res = kvv1.list(path)
        kvv1.client.list.assert_called_once_with(path)
        assert res == ["foo"]


class TestKVV2:
    @pytest.mark.parametrize(
        "versions,expected",
        [
            (0, [0]),
            ("1", [1]),
            ([2], [2]),
            (["3"], [3]),
        ],
    )
    def test_parse_versions(self, kvv2, versions, expected):
        """
        Ensure parsing versions works as expected:
        single integer/number string or list of those are allowed
        """
        assert kvv2._parse_versions(versions) == expected

    def test_parse_versions_raises_exception_when_unparsable(self, kvv2):
        """
        Ensure unparsable versions raise an exception
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv2._parse_versions("four")

    def test_get_secret_path_metadata_lookup_unexpected_response(
        self, kvv2, caplog, path
    ):
        """
        Ensure unexpected responses are treated as not KV
        """
        # _mock_json_response() returns a Mock, but we need MagicMock here
        resp_mm = MagicMock(spec=requests.models.Response)
        resp_mm.json.return_value = {"wrap_info": {}}
        resp_mm.status_code = 200
        resp_mm.reason = ""
        kvv2.client.get.return_value = resp_mm
        res = kvv2._get_secret_path_metadata(path)
        assert res is None
        assert "Unexpected response to metadata query" in caplog.text

    def test_get_secret_path_metadata_lookup_request_error(self, kvv2, caplog, path):
        """
        Ensure HTTP error status codes are treated as not KV
        """
        kvv2.client.get.side_effect = vault.VaultPermissionDeniedError
        res = kvv2._get_secret_path_metadata(path)
        assert res is None
        assert "VaultPermissionDeniedError:" in caplog.text

    @pytest.mark.parametrize("include_metadata", [False, True])
    def test_vault_kv_read(self, kvv2, include_metadata, kvv2_response, paths):
        """
        Ensure that VaultKV.read works for KV v2 and returns metadata
        if requested.
        """
        res = kvv2.read(path, include_metadata=include_metadata)
        kvv2.client.get.assert_called_once_with(paths["data"])
        if include_metadata:
            assert res == kvv2_response["data"]
        else:
            assert res == kvv2_response["data"]["data"]

    def test_vault_kv_write(self, kvv2, path, paths):
        """
        Ensure that VaultKV.write works for KV v2.
        """
        data = {"bar": "baz"}
        kvv2.write(path, data)
        kvv2.client.post.assert_called_once_with(paths["data"], payload={"data": data})

    def test_vault_kv_patch(self, kvv2, path, paths):
        """
        Ensure that VaultKV.patch works for KV v2.
        """
        data = {"bar": "baz"}
        kvv2.patch(path, data)
        kvv2.client.patch.assert_called_once_with(
            paths["data"],
            payload={"data": data},
            add_headers={"Content-Type": "application/merge-patch+json"},
        )

    def test_vault_kv_delete(self, kvv2, path, paths):
        """
        Ensure that VaultKV.delete works for KV v2.
        """
        kvv2.delete(path)
        kvv2.client.request.assert_called_once_with(
            "DELETE", paths["data"], payload=None
        )

    @pytest.mark.parametrize(
        "versions", [[1, 2], [2], 2, ["1", "2"], ["2"], "2", [1, "2"]]
    )
    def test_vault_kv_delete_versions(self, kvv2, versions, path, paths):
        """
        Ensure that VaultKV.delete with versions works for KV v2.
        """
        if isinstance(versions, list):
            expected = [int(x) for x in versions]
        else:
            expected = [int(versions)]
        kvv2.delete(path, versions=versions)
        kvv2.client.request.assert_called_once_with(
            "POST", paths["delete_versions"], payload={"versions": expected}
        )

    @pytest.mark.parametrize(
        "versions", [[1, 2], [2], 2, ["1", "2"], ["2"], "2", [1, "2"]]
    )
    def test_vault_kv_destroy(self, kvv2, versions, path, paths):
        """
        Ensure that VaultKV.destroy works for KV v2.
        """
        if isinstance(versions, list):
            expected = [int(x) for x in versions]
        else:
            expected = [int(versions)]
        kvv2.destroy(path, versions)
        kvv2.client.post.assert_called_once_with(
            paths["destroy"], payload={"versions": expected}
        )

    def test_vault_kv_nuke(self, kvv2, path, paths):
        """
        Ensure that VaultKV.nuke works for KV v2.
        """
        kvv2.nuke(path)
        kvv2.client.delete.assert_called_once_with(paths["metadata"])

    def test_vault_kv_list(self, kvv2, path, paths):
        """
        Ensure that VaultKV.list works for KV v2 and only returns keys.
        """
        res = kvv2.list(path)
        kvv2.client.list.assert_called_once_with(paths["metadata"])
        assert res == ["foo"]
