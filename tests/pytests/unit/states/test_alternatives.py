"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.alternatives as alternatives
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {alternatives: {}}


# 'install' function tests: 1


def test_install():
    """
    Test to install new alternative for defined <name>
    """
    name = "pager"
    link = "/usr/bin/pager"
    path = "/usr/bin/less"
    priority = 5

    ret = {
        "name": name,
        "link": link,
        "path": path,
        "priority": priority,
        "result": None,
        "changes": {},
        "comment": "",
    }

    bad_link = "/bin/pager"
    err = "the primary link for {} must be {}".format(name, link)

    mock_cinst = MagicMock(side_effect=[True, False])
    mock_cexist = MagicMock(
        side_effect=[True, False, False, True, False, False, False, True]
    )
    mock_out = MagicMock(side_effect=["", err, ""])
    mock_path = MagicMock(return_value=path)
    mock_link = MagicMock(return_value=link)
    with patch.dict(
        alternatives.__salt__,
        {
            "alternatives.check_installed": mock_cinst,
            "alternatives.check_exists": mock_cexist,
            "alternatives.install": mock_out,
            "alternatives.show_current": mock_path,
            "alternatives.show_link": mock_link,
        },
    ):
        comt = "Alternative {} for {} is already registered".format(path, name)
        ret.update({"comment": comt, "result": True})
        assert alternatives.install(name, link, path, priority) == ret

        comt = "Alternative will be set for {} to {} with priority {}".format(
            name, path, priority
        )
        ret.update({"comment": comt, "result": None})
        with patch.dict(alternatives.__opts__, {"test": True}):
            assert alternatives.install(name, link, path, priority) == ret

        comt = "Alternative for {} set to path {} with priority {}".format(
            name, path, priority
        )
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    "name": name,
                    "link": link,
                    "path": path,
                    "priority": priority,
                },
            }
        )
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.install(name, link, path, priority) == ret

        comt = "Alternative for {} not installed: {}".format(name, err)
        ret.update({"comment": comt, "result": False, "changes": {}, "link": bad_link})
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.install(name, bad_link, path, priority) == ret

        comt = "Alternative {} for {} registered with priority {} and not set to default".format(
            path, name, priority
        )
        ret.update(
            {
                "comment": comt,
                "result": True,
                "changes": {
                    "name": name,
                    "link": link,
                    "path": path,
                    "priority": priority,
                },
                "link": link,
            }
        )
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.install(name, link, path, priority) == ret


# 'remove' function tests: 1


def test_remove():
    """
    Test to removes installed alternative for defined <name> and <path>
    or fallback to default alternative, if some defined before.
    """
    name = "pager"
    path = "/usr/bin/less"

    ret = {"name": name, "path": path, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, True, True, False, False])
    mock_bool = MagicMock(return_value=True)
    mock_show = MagicMock(side_effect=[False, True, True, False])
    with patch.dict(
        alternatives.__salt__,
        {
            "alternatives.check_exists": mock,
            "alternatives.show_current": mock_show,
            "alternatives.remove": mock_bool,
        },
    ):
        comt = "Alternative for {} will be removed".format(name)
        ret.update({"comment": comt})
        with patch.dict(alternatives.__opts__, {"test": True}):
            assert alternatives.remove(name, path) == ret

        comt = "Alternative for {} removed".format(name)
        ret.update({"comment": comt, "result": True})
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.remove(name, path) == ret

        comt = "Alternative for pager removed. Falling back to path True"
        ret.update({"comment": comt, "result": True, "changes": {"path": True}})
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.remove(name, path) == ret

        comt = "Alternative for {} is set to it's default path True".format(name)
        ret.update({"comment": comt, "result": True, "changes": {}})
        assert alternatives.remove(name, path) == ret

        comt = "Alternative for {} doesn't exist".format(name)
        ret.update({"comment": comt, "result": False})
        assert alternatives.remove(name, path) == ret


# 'auto' function tests: 1


def test_auto():
    """
    Test to instruct alternatives to use the highest priority
    path for <name>
    """
    name = "pager"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[" auto mode", " ", " "])
    mock_auto = MagicMock(return_value=True)
    with patch.dict(
        alternatives.__salt__,
        {"alternatives.display": mock, "alternatives.auto": mock_auto},
    ):
        comt = "{} already in auto mode".format(name)
        ret.update({"comment": comt})
        assert alternatives.auto(name) == ret

        comt = "{} will be put in auto mode".format(name)
        ret.update({"comment": comt, "result": None})
        with patch.dict(alternatives.__opts__, {"test": True}):
            assert alternatives.auto(name) == ret

        ret.update({"comment": "", "result": True, "changes": {"result": True}})
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.auto(name) == ret


# 'set_' function tests: 1


def test_set():
    """
    Test to sets alternative for <name> to <path>, if <path> is defined
    as an alternative for <name>.
    """
    name = "pager"
    path = "/usr/bin/less"

    ret = {"name": name, "path": path, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[path, path, ""])
    mock_bool = MagicMock(return_value=True)
    mock_show = MagicMock(side_effect=[path, False, False, False, False])
    with patch.dict(
        alternatives.__salt__,
        {
            "alternatives.display": mock,
            "alternatives.show_current": mock_show,
            "alternatives.set": mock_bool,
        },
    ):
        comt = "Alternative for {} already set to {}".format(name, path)
        ret.update({"comment": comt})
        assert alternatives.set_(name, path) == ret

        comt = "Alternative for {} will be set to path /usr/bin/less".format(name)
        ret.update({"comment": comt, "result": None})
        with patch.dict(alternatives.__opts__, {"test": True}):
            assert alternatives.set_(name, path) == ret

        comt = "Alternative for {} not updated".format(name)
        ret.update({"comment": comt, "result": True})
        with patch.dict(alternatives.__opts__, {"test": False}):
            assert alternatives.set_(name, path) == ret

        comt = "Alternative {} for {} doesn't exist".format(path, name)
        ret.update({"comment": comt, "result": False})
        assert alternatives.set_(name, path) == ret
