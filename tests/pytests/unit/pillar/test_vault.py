import logging

import pytest

import salt.pillar.vault as vault
import salt.utils.vault as vaultutil
from tests.support.mock import ANY, Mock, patch


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
def data():
    return {"foo": "bar"}


@pytest.fixture
def read_kv(data):
    with patch("salt.utils.vault.read_kv", autospec=True) as read:
        read.return_value = data
        yield read


@pytest.fixture
def read_kv_not_found(read_kv):
    read_kv.side_effect = vaultutil.VaultNotFoundError


@pytest.fixture
def role_a():
    return {
        "from_db": True,
        "pass": "hunter2",
        "list": ["a", "b"],
    }


@pytest.fixture
def role_b():
    return {
        "from_web": True,
        "pass": "hunter1",
        "list": ["c", "d"],
    }


def test_ext_pillar(read_kv, data):
    """
    Test ext_pillar functionality. KV v1/2 is handled by the utils module.
    """
    ext_pillar = vault.ext_pillar("testminion", {}, "path=secret/path")
    read_kv.assert_called_once_with("secret/path", opts=ANY, context=ANY)
    assert ext_pillar == data


@pytest.mark.usefixtures("read_kv_not_found")
def test_ext_pillar_not_found(caplog):
    """
    Test that HTTP 404 is handled correctly
    """
    with caplog.at_level(logging.INFO):
        ext_pillar = vault.ext_pillar("testminion", {}, "path=secret/path")
        assert ext_pillar == {}
        assert "Vault secret not found for: secret/path" in caplog.messages


@pytest.mark.usefixtures("read_kv")
def test_ext_pillar_nesting_key(data):
    """
    Test that nesting_key is honored as expected
    """
    ext_pillar = vault.ext_pillar(
        "testminion", {}, "path=secret/path", nesting_key="baz"
    )
    assert ext_pillar == {"baz": data}


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


@pytest.mark.parametrize(
    "first,second,expected",
    [
        (
            "role_a",
            "role_b",
            {"from_db": True, "from_web": True, "list": ["c", "d"], "pass": "hunter1"},
        ),
        (
            "role_b",
            "role_a",
            {"from_db": True, "from_web": True, "list": ["a", "b"], "pass": "hunter2"},
        ),
    ],
)
def test_ext_pillar_merging(read_kv, first, second, expected, request):
    """
    Test that patterns that result in multiple paths are merged as expected.
    """
    first = request.getfixturevalue(first)
    second = request.getfixturevalue(second)
    read_kv.side_effect = (first, second)
    ext_pillar = vault.ext_pillar(
        "test-minion",
        {"roles": ["db", "web"]},
        conf="path=salt/roles/{pillar[roles]}",
        merge_strategy="smart",
        merge_lists=False,
    )
    assert ext_pillar == expected


def test_ext_pillar_disabled_during_pillar_rendering(read_kv):
    """
    Ensure ext_pillar returns an empty dict when called during pillar
    template rendering to prevent a cyclic dependency.
    """
    extra = {"_vault_runner_is_compiling_pillar_templates": True}
    res = vault.ext_pillar(
        "test-minion", {}, conf="path=secret/path", extra_minion_data=extra
    )
    assert res == {}
    read_kv.assert_not_called()


@pytest.mark.usefixtures("read_kv")
def test_invalid_config(caplog):
    """
    Ensure an empty dict is returned and an error is logged in case
    the config does not contain path=<...>
    """
    with caplog.at_level(logging.ERROR):
        ext_pillar = vault.ext_pillar("testminion", {}, "secret/path")
        assert ext_pillar == {}
        assert "is not a valid Vault ext_pillar config" in caplog.text
