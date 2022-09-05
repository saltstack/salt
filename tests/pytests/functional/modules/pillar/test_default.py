import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def sys_mod(modules):
    return modules.sys


@pytest.fixture(scope="module")
def pillar(modules):
    return modules.pillar


def test_pillar_get_issue_61084(sys_mod):
    """
    Test issue 61084. `sys.argspec` should return valid data and not throw a
    TypeError due to pickling
    This should probably be a pre-commit check or something
    """
    result = sys_mod.argspec("pillar.get")
    assert isinstance(result, dict)
    assert isinstance(result.get("pillar.get"), dict)


def test_get_non_existing(pillar):
    """
    Tests pillar.get when the item does not exist. Should return an empty string
    """
    result = pillar.get("non-existing-pillar-item")
    assert result == ""


def test_get_default_none(pillar):
    """
    Tests pillar.get when default is set to `None`. Should return `None`
    """
    result = pillar.get("non-existing-pillar-item", default=None)
    assert result is None
