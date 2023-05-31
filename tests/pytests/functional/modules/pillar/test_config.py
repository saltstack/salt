# This tests the pillar module with `pillar_raise_on_missing` set to True in the
# minion config. This effects all tests in this file
import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def pillar(modules):
    return modules.pillar


@pytest.fixture(scope="module")
def minion_config_overrides():
    yield {"pillar_raise_on_missing": True}


def test_get_non_existing(pillar):
    """
    Test pillar.get when the item does not exist. Should raise a KeyError when
    `pillar_raise_on_missing` is True in the minion config
    """
    with pytest.raises(KeyError):
        pillar.get("non-existing-pillar-item")


def test_get_default_none(pillar):
    """
    Tests pillar.get when default is set to `None`. Should return `None`
    """
    result = pillar.get("non-existing-pillar-item", default=None)
    assert result is None
