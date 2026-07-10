import pytest

import salt.exceptions
import salt.sdb.yaml as yaml_sdb


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {yaml_sdb: {"__opts__": minion_opts}}


@pytest.fixture
def yaml_profile(tmp_path):
    data_file = tmp_path / "sdb.yaml"
    data_file.write_text("top: value\nnested:\n  inner: deep\n", encoding="utf-8")
    return {"files": [str(data_file)]}


def test_get_top_level(yaml_profile):
    assert yaml_sdb.get("top", profile=yaml_profile) == "value"


def test_get_nested_dict(yaml_profile):
    assert yaml_sdb.get("nested", profile=yaml_profile) == {"inner": "deep"}


def test_get_nested_key_via_colon(yaml_profile):
    assert yaml_sdb.get("nested:inner", profile=yaml_profile) == "deep"


def test_get_missing_returns_none(yaml_profile):
    assert yaml_sdb.get("does-not-exist", profile=yaml_profile) is None


def test_get_merges_multiple_files(tmp_path):
    first = tmp_path / "a.yaml"
    first.write_text("a: 1\n", encoding="utf-8")
    second = tmp_path / "b.yaml"
    second.write_text("b: 2\n", encoding="utf-8")
    profile = {"files": [str(first), str(second)]}
    assert yaml_sdb.get("a", profile=profile) == 1
    assert yaml_sdb.get("b", profile=profile) == 2


def test_set_is_not_supported():
    """
    The yaml sdb backend is read-only; set raises NotImplemented.
    """
    with pytest.raises(salt.exceptions.NotImplemented):
        yaml_sdb.set_("key", "value")
