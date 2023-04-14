import pytest

import salt.utils.vault as vault
import salt.utils.vault.kv as vkv
from tests.pytests.unit.utils.vault.conftest import _mock_json_response
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
@pytest.mark.parametrize("exception", ["VaultPermissionDeniedError"])
def test_kv_wrapper_handles_auth_exceptions(wrapper, param, result, exception):
    """
    Test that *_kv wrappers retry with a new client if the authentication might
    be outdated.
    """
    func = getattr(vault, wrapper)
    exc = getattr(vault, exception)
    args = ["secret/some/path"]
    if param:
        args.append(param)
    args += [{}, {}]
    with patch("salt.utils.vault.get_kv", autospec=True) as getkv:
        with patch("salt.utils.vault.clear_cache", autospec=True) as cache:
            kv = Mock(spec=vkv.VaultKV)
            getattr(kv, wrapper.rstrip("_kv")).side_effect = (exc, result)
            getkv.return_value = kv
            res = func(*args)
            assert res == result
            cache.assert_called_once()


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

    def test_vault_kv_patch(self, kvv1, path):
        """
        Ensure that VaultKV.patch fails for KV v1. This action was introduced
        in KV v2. It could be simulated in Python though.
        """
        with pytest.raises(vault.VaultInvocationError):
            kvv1.patch(path, {"bar": "baz"})

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
        kvv2.client.get.return_value = MagicMock(
            _mock_json_response({"wrap_info": {}}, status_code=200)
        )
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
