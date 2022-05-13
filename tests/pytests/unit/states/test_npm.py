"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.modules.npm as npmmod
import salt.states.npm as npm
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {npm: {"__opts__": {"test": False}}}


@pytest.fixture(params=["", {}, []])
def fake_install(request):
    fake_install = create_autospec(npmmod.install, return_value=request.param)
    with patch.dict(
        npm.__salt__,
        {
            "npm.list": create_autospec(npmmod.list_, return_value={}),
            "npm.install": fake_install,
        },
    ):
        yield fake_install


def test_when_install_does_not_error_installed_should_be_true(fake_install):
    ret = npm.installed("fnord")
    assert ret["result"] is True


def test_installed():
    """
    Test to verify that the given package is installed
    and is at the correct version.
    """
    name = "coffee-script"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_err = MagicMock(side_effect=CommandExecutionError)
    mock_dict = MagicMock(return_value={name: {"version": "1.2"}})
    with patch.dict(npm.__salt__, {"npm.list": mock_err}):
        comt = "Error looking up 'coffee-script': "
        ret.update({"comment": comt})
        assert npm.installed(name) == ret

    with patch.dict(npm.__salt__, {"npm.list": mock_dict, "npm.install": mock_err}):
        with patch.dict(npm.__opts__, {"test": True}):
            comt = "Package(s) 'coffee-script' satisfied by coffee-script@1.2"
            ret.update({"comment": comt, "result": True})
            assert npm.installed(name) == ret

        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Package(s) 'coffee-script' satisfied by coffee-script@1.2"
            ret.update({"comment": comt, "result": True})
            assert npm.installed(name) == ret

            comt = "Error installing 'n, p, m': "
            ret.update({"comment": comt, "result": False})
            assert npm.installed(name, "npm") == ret

            with patch.dict(npm.__salt__, {"npm.install": mock_dict}):
                comt = "Package(s) 'n, p, m' successfully installed"
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {"new": ["n", "p", "m"], "old": []},
                    }
                )
                assert npm.installed(name, "npm") == ret


def test_removed():
    """
    Test to verify that the given package is not installed.
    """
    name = "coffee-script"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_err = MagicMock(
        side_effect=[CommandExecutionError, {}, {name: ""}, {name: ""}]
    )
    mock_t = MagicMock(return_value=True)
    with patch.dict(npm.__salt__, {"npm.list": mock_err, "npm.uninstall": mock_t}):
        comt = "Error uninstalling 'coffee-script': "
        ret.update({"comment": comt})
        assert npm.removed(name) == ret

        comt = "Package 'coffee-script' is not installed"
        ret.update({"comment": comt, "result": True})
        assert npm.removed(name) == ret

        with patch.dict(npm.__opts__, {"test": True}):
            comt = "Package 'coffee-script' is set to be removed"
            ret.update({"comment": comt, "result": None})
            assert npm.removed(name) == ret

        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Package 'coffee-script' was successfully removed"
            ret.update({"comment": comt, "result": True, "changes": {name: "Removed"}})
            assert npm.removed(name) == ret


def test_bootstrap():
    """
    Test to bootstraps a node.js application.
    """
    name = "coffee-script"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_err = MagicMock(side_effect=[CommandExecutionError, False, True])
    with patch.dict(npm.__salt__, {"npm.install": mock_err}):
        comt = "Error Bootstrapping 'coffee-script': "
        ret.update({"comment": comt})
        assert npm.bootstrap(name) == ret

        comt = "Directory is already bootstrapped"
        ret.update({"comment": comt, "result": True})
        assert npm.bootstrap(name) == ret

        comt = "Directory was successfully bootstrapped"
        ret.update({"comment": comt, "result": True, "changes": {name: "Bootstrapped"}})
        assert npm.bootstrap(name) == ret


def test_cache_cleaned():
    """
    Test to verify that the npm cache is cleaned.
    """
    name = "coffee-script"

    pkg_ret = {"name": name, "result": False, "comment": "", "changes": {}}
    ret = {"name": None, "result": False, "comment": "", "changes": {}}

    mock_list = MagicMock(return_value=["~/.npm", "~/.npm/{}/".format(name)])
    mock_cache_clean_success = MagicMock(return_value=True)
    mock_cache_clean_failure = MagicMock(return_value=False)
    mock_err = MagicMock(side_effect=CommandExecutionError)

    with patch.dict(npm.__salt__, {"npm.cache_list": mock_err}):
        comt = "Error looking up cached packages: "
        ret.update({"comment": comt})
        assert npm.cache_cleaned() == ret

    with patch.dict(npm.__salt__, {"npm.cache_list": mock_err}):
        comt = "Error looking up cached {}: ".format(name)
        pkg_ret.update({"comment": comt})
        assert npm.cache_cleaned(name) == pkg_ret

    mock_data = {"npm.cache_list": mock_list, "npm.cache_clean": MagicMock()}
    with patch.dict(npm.__salt__, mock_data):
        non_cached_pkg = "salt"
        comt = "Package {} is not in the cache".format(non_cached_pkg)
        pkg_ret.update({"name": non_cached_pkg, "result": True, "comment": comt})
        assert npm.cache_cleaned(non_cached_pkg) == pkg_ret
        pkg_ret.update({"name": name})

        with patch.dict(npm.__opts__, {"test": True}):
            comt = "Cached packages set to be removed"
            ret.update({"result": None, "comment": comt})
            assert npm.cache_cleaned() == ret

        with patch.dict(npm.__opts__, {"test": True}):
            comt = "Cached {} set to be removed".format(name)
            pkg_ret.update({"result": None, "comment": comt})
            assert npm.cache_cleaned(name) == pkg_ret

        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Cached packages successfully removed"
            ret.update(
                {"result": True, "comment": comt, "changes": {"cache": "Removed"}}
            )
            assert npm.cache_cleaned() == ret

        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Cached {} successfully removed".format(name)
            pkg_ret.update(
                {"result": True, "comment": comt, "changes": {name: "Removed"}}
            )
            assert npm.cache_cleaned(name) == pkg_ret

    mock_data = {
        "npm.cache_list": mock_list,
        "npm.cache_clean": MagicMock(return_value=False),
    }
    with patch.dict(npm.__salt__, mock_data):
        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Error cleaning cached packages"
            ret.update({"result": False, "comment": comt})
            ret["changes"] = {}
            assert npm.cache_cleaned() == ret

        with patch.dict(npm.__opts__, {"test": False}):
            comt = "Error cleaning cached {}".format(name)
            pkg_ret.update({"result": False, "comment": comt})
            pkg_ret["changes"] = {}
            assert npm.cache_cleaned(name) == pkg_ret
