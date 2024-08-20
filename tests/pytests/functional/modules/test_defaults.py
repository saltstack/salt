import pytest

pytestmark = [pytest.mark.skip_unless_on_linux]


@pytest.fixture(scope="module")
def defaults(modules):
    return modules.defaults


def test_defaults_get(defaults, state_tree, caplog):
    """
    test defaults.get
    """

    json_contents = """
    {
        "users": {
            "root": 1
        }
    }
    """
    path = state_tree / "core"
    with pytest.helpers.temp_file("defaults.json", json_contents, path):
        assert defaults.get("core:users:root") == 1


def test_defaults_merge(defaults):
    """
    test defaults.merge
    """
    assert defaults.merge({"a": "b"}, {"d": "e"}) == {"a": "b", "d": "e"}


def test_defaults_deepcopy(defaults):
    """
    test defaults.deepcopy
    """
    test_dict = {"1": "one"}
    assert defaults.deepcopy(test_dict) == test_dict
