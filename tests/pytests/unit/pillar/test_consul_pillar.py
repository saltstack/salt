import pytest

import salt.pillar.consul_pillar as consul_pillar
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not consul_pillar.consul, reason="python-consul module not installed"
    )
]


@pytest.fixture
def base_pillar_data():
    return [
        {
            "Value": "/path/to/certs/testsite1.crt",
            "Key": "test-shared/sites/testsite1/ssl/certs/SSLCertificateFile",
        },
        {
            "Value": "/path/to/certs/testsite1.key",
            "Key": "test-shared/sites/testsite1/ssl/certs/SSLCertificateKeyFile",
        },
        {"Value": None, "Key": "test-shared/sites/testsite1/ssl/certs/"},
        {"Value": "True", "Key": "test-shared/sites/testsite1/ssl/force"},
        {"Value": None, "Key": "test-shared/sites/testsite1/ssl/"},
        {
            "Value": "salt://sites/testsite1.tmpl",
            "Key": "test-shared/sites/testsite1/template",
        },
        {"Value": "test.example.com", "Key": "test-shared/sites/testsite1/uri"},
        {"Value": None, "Key": "test-shared/sites/testsite1/"},
        {"Value": None, "Key": "test-shared/sites/"},
        {"Value": "Test User", "Key": "test-shared/user/full_name"},
        {"Value": "adm\nwww-data\nmlocate", "Key": "test-shared/user/groups"},
        {"Value": '"adm\nwww-data\nmlocate"', "Key": "test-shared/user/dontsplit"},
        {"Value": "yaml:\n  key: value\n", "Key": "test-shared/user/dontexpand"},
        {"Value": None, "Key": "test-shared/user/blankvalue"},
        {"Value": "test", "Key": "test-shared/user/login"},
        {"Value": None, "Key": "test-shared/user/"},
    ]


@pytest.fixture
def configure_loader_modules():
    return {
        consul_pillar: {
            "__opts__": {
                "consul_config": {"consul.port": 8500, "consul.host": "172.17.0.15"}
            },
            "get_conn": MagicMock(return_value="consul_connection"),
        }
    }


def test_connection(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            consul_pillar.ext_pillar(
                "testminion", {}, "consul_config root=test-shared/"
            )
            consul_pillar.get_conn.assert_called_once_with(
                consul_pillar.__opts__, "consul_config"
            )


def test_pillar_data(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            pillar_data = consul_pillar.ext_pillar(
                "testminion", {}, "consul_config root=test-shared/"
            )
            consul_pillar.consul_fetch.assert_called_once_with(
                "consul_connection", "test-shared"
            )
            assert sorted(pillar_data) == ["sites", "user"]
            assert "blankvalue" not in pillar_data["user"]


def test_blank_root(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            pillar_data = consul_pillar.ext_pillar("testminion", {}, "consul_config")
            consul_pillar.consul_fetch.assert_called_once_with("consul_connection", "")
            assert sorted(pillar_data) == ["test-shared"]


def test_pillar_nest(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            pillar_data = consul_pillar.ext_pillar(
                "testminion",
                {},
                "consul_config pillar_root=nested-key/ root=test-shared/ ",
            )
            assert sorted(pillar_data["nested-key"]) == ["sites", "user"]
            assert "blankvalue" not in pillar_data["nested-key"]["user"]


def test_value_parsing(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            pillar_data = consul_pillar.ext_pillar(
                "testminion", {}, "consul_config root=test-shared/"
            )
            assert isinstance(pillar_data["user"]["dontsplit"], str)


def test_non_expansion(base_pillar_data):
    with patch.dict(consul_pillar.__salt__, {"grains.get": MagicMock(return_value={})}):
        with patch.object(
            consul_pillar,
            "consul_fetch",
            MagicMock(return_value=("2232", base_pillar_data)),
        ):
            pillar_data = consul_pillar.ext_pillar(
                "testminion",
                {},
                "consul_config root=test-shared/ expand_keys=false",
            )
            assert isinstance(pillar_data["user"]["dontexpand"], str)


def test_dict_merge():
    test_dict = {}
    simple_dict = {"key1": {"key2": "val1"}}
    with patch.dict(test_dict, simple_dict):
        assert consul_pillar.dict_merge(test_dict, simple_dict) == simple_dict
    with patch.dict(test_dict, {"key1": {"key3": {"key4": "value"}}}):
        assert consul_pillar.dict_merge(test_dict, simple_dict) == {
            "key1": {"key2": "val1", "key3": {"key4": "value"}}
        }
