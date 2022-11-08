import pytest

from salt.pillar import extra_minion_data_in_pillar
from tests.support.mock import MagicMock


@pytest.fixture
def configure_loader_modules():
    return {extra_minion_data_in_pillar: {}}


@pytest.fixture
def extra_minion_data():
    return {
        "key1": {"subkey1": "value1"},
        "key2": {"subkey2": {"subsubkey2": "value2"}},
        "key3": "value3",
        "key4": {"subkey4": "value4"},
    }


def test_extra_values_none_or_empty():
    ret = extra_minion_data_in_pillar.ext_pillar(
        "fake_id", MagicMock(), "fake_include", None
    )
    assert ret == {}
    ret = extra_minion_data_in_pillar.ext_pillar(
        "fake_id", MagicMock(), "fake_include", {}
    )
    assert ret == {}


def test_include_all(extra_minion_data):
    for include_all in ["*", "<all>"]:
        ret = extra_minion_data_in_pillar.ext_pillar(
            "fake_id", MagicMock(), include_all, extra_minion_data
        )
        assert ret == extra_minion_data


def test_include_specific_keys(extra_minion_data):
    # Tests partially existing key, key with and without subkey,
    ret = extra_minion_data_in_pillar.ext_pillar(
        "fake_id",
        MagicMock(),
        include=["key1:subkey1", "key2:subkey3", "key3", "key4"],
        extra_minion_data=extra_minion_data,
    )
    assert ret == {
        "key1": {"subkey1": "value1"},
        "key3": "value3",
        "key4": {"subkey4": "value4"},
    }
