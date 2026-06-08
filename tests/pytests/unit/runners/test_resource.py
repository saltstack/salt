"""
Unit tests for ``salt-run resource.*`` operator helpers.
"""

import pytest

import salt.runners.resource as resource_runner
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def configure_loader_modules():
    return {resource_runner: {"__opts__": {}}}


def _patched_cache(entries):
    """Return a fake ``salt.cache.factory(...)`` returning ``entries``."""
    cache = MagicMock()
    cache.list = MagicMock(
        side_effect=lambda bank: (
            list(entries.keys()) if bank == "resource_grains" else []
        )
    )
    cache.fetch = MagicMock(
        side_effect=lambda bank, key: (
            entries.get(key) if bank == "resource_grains" else None
        )
    )
    return cache


def test_show_grains_returns_cached_dict():
    entries = {"dummy:dummy-01": {"env": "prod", "id": "dummy-01"}}
    fake = _patched_cache(entries)
    with patch.object(resource_runner, "_resource_grains_cache", return_value=fake):
        result = resource_runner.show_grains(type="dummy", id="dummy-01")
    assert result == {"env": "prod", "id": "dummy-01"}


def test_show_grains_returns_none_for_missing_srn():
    fake = _patched_cache({})
    with patch.object(resource_runner, "_resource_grains_cache", return_value=fake):
        result = resource_runner.show_grains(type="dummy", id="ghost")
    assert result is None


def test_show_grains_returns_none_for_empty_args():
    assert resource_runner.show_grains(type="", id="dummy-01") is None
    assert resource_runner.show_grains(type="dummy", id="") is None


def test_show_grains_swallows_cache_errors():
    cache = MagicMock()
    cache.fetch = MagicMock(side_effect=RuntimeError("boom"))
    with patch.object(resource_runner, "_resource_grains_cache", return_value=cache):
        assert resource_runner.show_grains(type="dummy", id="dummy-01") is None


def test_list_grains_summarises_every_entry():
    entries = {
        "dummy:dummy-01": {"env": "prod", "role": "web"},
        "ssh:node1": {"env": "staging", "role": "db", "tier": "1"},
    }
    fake = _patched_cache(entries)
    with patch.object(resource_runner, "_resource_grains_cache", return_value=fake):
        result = resource_runner.list_grains()
    assert set(result.keys()) == {"dummy:dummy-01", "ssh:node1"}
    assert result["dummy:dummy-01"] == {
        "grain_keys": ["env", "role"],
        "grain_count": 2,
    }
    assert result["ssh:node1"] == {
        "grain_keys": ["env", "role", "tier"],
        "grain_count": 3,
    }


def test_list_grains_handles_empty_bank():
    fake = _patched_cache({})
    with patch.object(resource_runner, "_resource_grains_cache", return_value=fake):
        assert resource_runner.list_grains() == {}


def test_list_grains_skips_non_dict_entries():
    entries = {
        "dummy:bad": "not-a-dict",
        "dummy:good": {"k": "v"},
    }
    fake = _patched_cache(entries)
    with patch.object(resource_runner, "_resource_grains_cache", return_value=fake):
        result = resource_runner.list_grains()
    assert "dummy:bad" not in result
    assert result["dummy:good"]["grain_count"] == 1


def test_refresh_fires_event_to_named_minion():
    fake_evt = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=fake_evt)
    cm.__exit__ = MagicMock(return_value=False)
    with patch("salt.utils.event.get_event", return_value=cm), patch.dict(
        resource_runner.__opts__, {"sock_dir": "/tmp/sock"}
    ):
        result = resource_runner.refresh(minion="resources-minion")
    assert result is True
    fake_evt.fire_event.assert_called_once_with(
        {"minion": "resources-minion"}, "minion/resources-minion/resource_refresh"
    )


def test_refresh_returns_false_on_empty_minion():
    assert resource_runner.refresh(minion="") is False


def test_refresh_swallows_event_errors():
    fake_evt = MagicMock()
    fake_evt.fire_event.side_effect = RuntimeError("boom")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=fake_evt)
    cm.__exit__ = MagicMock(return_value=False)
    with patch("salt.utils.event.get_event", return_value=cm), patch.dict(
        resource_runner.__opts__, {"sock_dir": "/tmp/sock"}
    ):
        assert resource_runner.refresh(minion="resources-minion") is False
