import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def sys_mod(modules):
    return modules.sys


def test_pillar_get_issue_61084(sys_mod):
    """
    Test issue 61084. `sys.argspec` should return valid data and not throw a
    TypeError due to pickling
    This should probably be a pre-commit check or something
    """
    result = sys_mod.argspec("pillar.get")
    assert isinstance(result, dict)
    assert isinstance(result.get("pillar.get"), dict)
