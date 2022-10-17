import logging

import pytest
from requests.exceptions import HTTPError

import salt.pillar.vault as vault
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {vault: {}}


@pytest.fixture
def vault_kvv1():
    res = Mock(status_code=200)
    res.json.return_value = {"data": {"foo": "bar"}}
    return Mock(return_value=res)


@pytest.fixture
def vault_kvv2():
    res = Mock(status_code=200)
    res.json.return_value = {"data": {"data": {"foo": "bar"}}, "metadata": {}}
    return Mock(return_value=res)


@pytest.fixture
def is_v2_false():
    path = "secret/path"
    return {"v2": False, "data": path, "metadata": path, "delete": path, "type": "kv"}


@pytest.fixture
def is_v2_true():
    return {
        "v2": True,
        "data": "secret/data/path",
        "metadata": "secret/metadata/path",
        "type": "kv",
    }


@pytest.mark.parametrize(
    "is_v2,vaultkv", [("is_v2_false", "vault_kvv1"), ("is_v2_true", "vault_kvv2")]
)
def test_ext_pillar(is_v2, vaultkv, request):
    """
    Test ext_pillar functionality for KV v1/2
    """
    is_v2 = request.getfixturevalue(is_v2)
    vaultkv = request.getfixturevalue(vaultkv)
    with patch.dict(
        vault.__utils__,
        {"vault.is_v2": Mock(return_value=is_v2), "vault.make_request": vaultkv},
    ):
        ext_pillar = vault.ext_pillar("testminion", {}, "path=secret/path")
        vaultkv.assert_called_once_with("GET", "v1/" + is_v2["data"])
        assert "foo" in ext_pillar
        assert "metadata" not in ext_pillar
        assert "data" not in ext_pillar
        assert ext_pillar["foo"] == "bar"


def test_ext_pillar_not_found(is_v2_false, caplog):
    """
    Test that HTTP 404 is handled correctly
    """
    res = Mock(status_code=404, ok=False)
    res.raise_for_status.side_effect = HTTPError()
    with caplog.at_level(logging.INFO):
        with patch.dict(
            vault.__utils__,
            {
                "vault.is_v2": Mock(return_value=is_v2_false),
                "vault.make_request": Mock(return_value=res),
            },
        ):
            ext_pillar = vault.ext_pillar("testminion", {}, "path=secret/path")
            assert ext_pillar == {}
            assert "Vault secret not found for: secret/path" in caplog.messages


def test_ext_pillar_nesting_key(is_v2_false, vault_kvv1):
    """
    Test that nesting_key is honored as expected
    """
    with patch.dict(
        vault.__utils__,
        {
            "vault.is_v2": Mock(return_value=is_v2_false),
            "vault.make_request": vault_kvv1,
        },
    ):
        ext_pillar = vault.ext_pillar(
            "testminion", {}, "path=secret/path", nesting_key="baz"
        )
        assert "foo" not in ext_pillar
        assert "baz" in ext_pillar
        assert "foo" in ext_pillar["baz"]
        assert ext_pillar["baz"]["foo"] == "bar"
