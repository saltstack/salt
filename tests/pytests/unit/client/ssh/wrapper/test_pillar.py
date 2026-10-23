"""
Tests for the salt-ssh ``pillar`` wrapper.
"""

import pytest

import salt.client.ssh.wrapper.pillar as ssh_pillar
import salt.utils.secret as secret
from tests.support.mock import patch


class _Pillar(dict):
    """
    Stand-in for the loader's ``__pillar__`` wrapper, which exposes ``value()``.
    """

    def value(self):
        return self


@pytest.fixture
def configure_loader_modules():
    pillar = _Pillar(
        secret.hide(
            {
                "pin": 1234,
                "role": "web",
                "db": {"user": "admin", "password": "hunter2"},
            }
        )
    )
    return {ssh_pillar: {"__opts__": {}, "__pillar__": pillar}}


@pytest.fixture(params=[False, True], ids=["flag_off", "flag_on"])
def mask_flag(request):
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": request.param}):
        yield request.param


def test_item_returns_real_values_when_masking_is_off():
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": False}):
        assert ssh_pillar.item("pin") == {"pin": 1234}


def test_item_masks_when_masking_is_on():
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": True}):
        assert ssh_pillar.item("pin") == {"pin": secret.REDACT_PLACEHOLDER}


def test_item_masks_nested_values_only_when_masking_is_on():
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": False}):
        assert ssh_pillar.item("db") == {"db": {"user": "admin", "password": "hunter2"}}
    with patch.dict(ssh_pillar.__opts__, {"pillar_mask_output": True}):
        assert ssh_pillar.item("db") == {
            "db": {
                "user": secret.REDACT_PLACEHOLDER,
                "password": secret.REDACT_PLACEHOLDER,
            }
        }


def test_get_returns_real_values(mask_flag):
    assert ssh_pillar.get("pin") == 1234
    assert ssh_pillar.get("db:password") == "hunter2"
    assert ssh_pillar.get("missing", "fallback") == "fallback"


def test_get_merge_returns_real_values_in_plain_dict(mask_flag):
    ret = ssh_pillar.get("db", {"port": 5432}, merge=True)
    assert ret == {"port": 5432, "user": "admin", "password": "hunter2"}
    assert not isinstance(ret, secret.MaskedDict)


@pytest.mark.parametrize("func", ["raw", "items", "data"])
def test_raw_items_and_data_return_real_values(mask_flag, func):
    ret = getattr(ssh_pillar, func)()
    assert ret["pin"] == 1234
    assert ret["db"] == {"user": "admin", "password": "hunter2"}
    assert not isinstance(ret, secret.MaskedDict)
    assert not isinstance(ret["db"], secret.MaskedDict)


def test_raw_with_key_returns_real_values(mask_flag):
    assert ssh_pillar.raw("db") == {"user": "admin", "password": "hunter2"}


def test_keys_returns_real_keys(mask_flag):
    assert sorted(ssh_pillar.keys("db")) == ["password", "user"]


def test_filter_by_matches_on_real_values(mask_flag):
    lookup = {"web": "serve", "db": "query", "default": "idle"}
    assert ssh_pillar.filter_by(lookup, "role") == "serve"
