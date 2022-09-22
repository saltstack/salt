import copy
import logging

import pytest
from requests.exceptions import HTTPError

import salt.pillar.vault as vault
from tests.support.mock import Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        vault: {
            "__utils__": {
                "vault.expand_pattern_lists": Mock(
                    side_effect=lambda x, *args, **kwargs: [x]
                )
            }
        }
    }


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


@pytest.mark.parametrize(
    "pattern,expected",
    [
        ("no/template/in/use", ["no/template/in/use"]),
        ("salt/minions/{minion}", ["salt/minions/test-minion"]),
        ("salt/roles/{pillar[role]}", ["salt/roles/foo"]),
        ("salt/roles/{pillar[nonexistent]}", []),
    ],
)
def test_get_paths(pattern, expected):
    """
    Test that templated paths are resolved as expected.
    Expansion of lists is tested in the utility module unit test.
    """
    previous_pillar = {
        "role": "foo",
    }
    result = vault._get_paths(pattern, "test-minion", previous_pillar)
    assert result == expected


def test_ext_pillar_merging(is_v2_false):
    """
    Test that patterns that result in multiple paths are merged as expected.
    """

    def make_request(method, resource, *args, **kwargs):
        vault_data = {
            "v1/salt/roles/db": {
                "from_db": True,
                "pass": "hunter2",
                "list": ["a", "b"],
            },
            "v1/salt/roles/web": {
                "from_web": True,
                "pass": "hunter1",
                "list": ["c", "d"],
            },
        }
        res = Mock(status_code=200, ok=True)
        res.json.return_value = {"data": copy.deepcopy(vault_data[resource])}
        return res

    cases = [
        (
            ["salt/roles/db", "salt/roles/web"],
            {"from_db": True, "from_web": True, "list": ["c", "d"], "pass": "hunter1"},
        ),
        (
            ["salt/roles/web", "salt/roles/db"],
            {"from_db": True, "from_web": True, "list": ["a", "b"], "pass": "hunter2"},
        ),
    ]
    vaultkv = Mock(side_effect=make_request)

    for expanded_patterns, expected in cases:
        with patch.dict(
            vault.__utils__,
            {
                "vault.make_request": vaultkv,
                "vault.expand_pattern_lists": Mock(return_value=expanded_patterns),
                "vault.is_v2": Mock(return_value=is_v2_false),
            },
        ):
            ext_pillar = vault.ext_pillar(
                "test-minion",
                {"roles": ["db", "web"]},
                conf="path=salt/roles/{pillar[roles]}",
                merge_strategy="smart",
                merge_lists=False,
            )
            assert ext_pillar == expected


def test_ext_pillar_disabled_during_policy_pillar_rendering():
    """
    Ensure ext_pillar returns an empty dict when called during pillar
    template rendering to prevent a cyclic dependency.
    """
    mock_version = Mock()
    mock_vault = Mock()
    extra = {"_vault_runner_is_compiling_pillar_templates": True}

    with patch.dict(
        vault.__utils__, {"vault.make_request": mock_vault, "vault.is_v2": mock_version}
    ):
        assert {} == vault.ext_pillar(
            "test-minion", {}, conf="path=secret/path", extra_minion_data=extra
        )
        assert mock_version.call_count == 0
        assert mock_vault.call_count == 0


def test_invalid_config(caplog):
    """
    Ensure an empty dict is returned and an error is logged in case
    the config does not contain path=<...>
    """
    with caplog.at_level(logging.ERROR):
        ext_pillar = vault.ext_pillar("testminion", {}, "secret/path")
        assert ext_pillar == {}
        assert "is not a valid Vault ext_pillar config" in caplog.text
