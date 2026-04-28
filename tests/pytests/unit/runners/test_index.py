import pytest

import salt.runners.index as index_runner
import salt.utils.resource_registry as rr
from salt.exceptions import SaltInvocationError
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def configure_loader_modules():
    return {index_runner: {"__opts__": {}}}


class _FakeCache:
    def __init__(self):
        self.banks = {}

    def fetch(self, bank, key):
        return self.banks.get(bank, {}).get(key)

    def store(self, bank, key, value):
        self.banks.setdefault(bank, {})[key] = value


@pytest.fixture
def opts_pki(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    for subdir in ["minions", "minions_pre", "minions_rejected"]:
        (pki_dir / subdir).mkdir()

    return {
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
        "pki_index_enabled": True,
        "pki_index_size": 100,
        "pki_index_slot_size": 64,
    }


@pytest.fixture
def opts_resources(tmp_path):
    return {
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock"),
    }


def test_list_indexes():
    got = index_runner.list_indexes()
    assert "pki" in got
    assert "resources" in got


def test_compact_unknown_name():
    with pytest.raises(SaltInvocationError):
        index_runner.compact("nosuchindex")


def test_compact_empty_name():
    with pytest.raises(SaltInvocationError):
        index_runner.compact("")


def test_status_pki_empty(opts_pki):
    with patch.dict(index_runner.__opts__, opts_pki):
        result = index_runner.status("pki")
    assert "PKI Index Status" in result
    assert "Occupied: 0" in result


def test_compact_pki_rebuild(opts_pki, tmp_path):
    pki_dir = tmp_path / "pki"
    (pki_dir / "minions" / "minion1").write_text("fake_key_1")
    (pki_dir / "minions" / "minion2").write_text("fake_key_2")
    (pki_dir / "minions_pre" / "minion3").write_text("fake_key_3")

    with patch.dict(index_runner.__opts__, {**opts_pki, "pki_index_enabled": True}):
        result = index_runner.compact("pki", dry_run=False)
    assert "successfully" in result
    assert "3" in result


def test_compact_pki_alias_keys(opts_pki, tmp_path):
    (tmp_path / "pki" / "minions" / "m1").write_text("k")
    with patch.dict(index_runner.__opts__, opts_pki):
        result = index_runner.compact("keys")
    assert "successfully" in result


def test_compact_resources_dry_run(opts_resources):
    reg = rr.ResourceRegistry(opts_resources, cache=_FakeCache())
    with patch.dict(index_runner.__opts__, opts_resources):
        with patch("salt.utils.resource_registry.get_registry", return_value=reg):
            result = index_runner.status("resources")
    assert "Resource index status" in result
    assert "Path" in result


def test_compact_resources_after_register(opts_resources):
    reg = rr.ResourceRegistry(opts_resources, cache=_FakeCache())
    with patch.dict(index_runner.__opts__, opts_resources):
        with patch("salt.utils.resource_registry.get_registry", return_value=reg):
            reg.register_minion("m1", {"ssh": ["a", "b"]})
            result = index_runner.compact("resources", dry_run=False)
    assert "Resource index compacted" in result
