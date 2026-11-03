"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.pyenv as pyenv
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pyenv: {}}


def test_installed():
    """
    Test to verify that the specified python is installed with pyenv.
    """
    name = "python-2.7.6"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(pyenv.__opts__, {"test": True}):
        comt = "python 2.7.6 is set to be installed"
        ret.update({"comment": comt})
        assert pyenv.installed(name) == ret

    with patch.dict(pyenv.__opts__, {"test": False}):
        mock_f = MagicMock(side_effect=[False, False, True])
        mock_fa = MagicMock(side_effect=[False, True])
        mock_str = MagicMock(return_value="2.7.6")
        mock_lst = MagicMock(return_value=["2.7.6"])
        with patch.dict(
            pyenv.__salt__,
            {
                "pyenv.is_installed": mock_f,
                "pyenv.install": mock_fa,
                "pyenv.default": mock_str,
                "pyenv.versions": mock_lst,
            },
        ):
            comt = "pyenv failed to install"
            ret.update({"comment": comt, "result": False})
            assert pyenv.installed(name) == ret

            comt = "Requested python exists."
            ret.update({"comment": comt, "result": True, "default": True})
            assert pyenv.installed(name) == ret

            assert pyenv.installed(name) == ret


def test_absent():
    """
    Test to verify that the specified python is not installed with pyenv.
    """
    name = "python-2.7.6"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(pyenv.__opts__, {"test": True}):
        comt = "python 2.7.6 is set to be uninstalled"
        ret.update({"comment": comt})
        assert pyenv.absent(name) == ret

    with patch.dict(pyenv.__opts__, {"test": False}):
        mock_f = MagicMock(side_effect=[False, True])
        mock_t = MagicMock(return_value=True)
        mock_str = MagicMock(return_value="2.7.6")
        mock_lst = MagicMock(return_value=["2.7.6"])
        with patch.dict(
            pyenv.__salt__,
            {
                "pyenv.is_installed": mock_f,
                "pyenv.uninstall_python": mock_t,
                "pyenv.default": mock_str,
                "pyenv.versions": mock_lst,
            },
        ):
            comt = "pyenv not installed, 2.7.6 not either"
            ret.update({"comment": comt, "result": True})
            assert pyenv.absent(name) == ret

            comt = "Successfully removed python"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "default": True,
                    "changes": {"2.7.6": "Uninstalled"},
                }
            )
            assert pyenv.absent(name) == ret


def test_install_pyenv():
    """
    Test to install pyenv itself if not installed.

    install_pyenv must never try to install a python version (it does not
    receive one); it should only call pyenv.install. See issue #37648.
    """
    name = "install-pyenv"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_is = MagicMock(side_effect=[False, True, True, False, False])
    mock_i = MagicMock(side_effect=[False, True])
    # install_python must never be called by install_pyenv.
    mock_ip = MagicMock(side_effect=AssertionError("pyenv.install_python called"))
    with patch.dict(
        pyenv.__salt__,
        {
            "pyenv.is_installed": mock_is,
            "pyenv.install": mock_i,
            "pyenv.install_python": mock_ip,
        },
    ):
        with patch.dict(pyenv.__opts__, {"test": True}):
            comt = "pyenv is set to be installed"
            ret.update({"comment": comt, "result": None})
            assert pyenv.install_pyenv(name) == ret

            comt = "pyenv is already installed"
            ret.update({"comment": comt, "result": True})
            assert pyenv.install_pyenv(name) == ret

        with patch.dict(pyenv.__opts__, {"test": False}):
            comt = "pyenv is already installed"
            ret.update({"comment": comt, "result": True})
            assert pyenv.install_pyenv(name) == ret

            comt = "pyenv failed to install"
            ret.update({"comment": comt, "result": False})
            assert pyenv.install_pyenv(name) == ret

            comt = "pyenv installed"
            ret.update({"comment": comt, "result": True})
            assert pyenv.install_pyenv(name) == ret


def test_install_pyenv_with_user_37648():
    """
    Test that install_pyenv passes ``user`` to the pyenv execution module.

    Before the fix for issue #37648, install_pyenv called
    _check_and_install_python(ret, user), which put ``user`` into the
    ``python`` positional argument and tried to install a python version
    named after the user instead of installing pyenv itself.
    """
    name = "install-pyenv"
    # ``user`` is the decisive kwarg: it is what a production state like
    #   pyenv.install_pyenv:
    #     - user: pyenv_user
    # passes through, and it is the argument that was previously misrouted
    # into the python version parameter.
    user = "pyenv_user"

    mock_is = MagicMock(return_value=False)
    mock_i = MagicMock(return_value=True)
    # None of the python-version machinery may be touched by install_pyenv.
    mock_ip = MagicMock(side_effect=AssertionError("pyenv.install_python called"))
    mock_d = MagicMock(side_effect=AssertionError("pyenv.default called"))
    mock_v = MagicMock(side_effect=AssertionError("pyenv.versions called"))
    with patch.dict(
        pyenv.__salt__,
        {
            "pyenv.is_installed": mock_is,
            "pyenv.install": mock_i,
            "pyenv.install_python": mock_ip,
            "pyenv.default": mock_d,
            "pyenv.versions": mock_v,
        },
    ), patch.dict(pyenv.__opts__, {"test": False}):
        ret = pyenv.install_pyenv(name, user=user)

    assert ret == {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "pyenv installed",
    }
    mock_is.assert_called_once_with(user)
    mock_i.assert_called_once_with(user)


def test_installed_unaffected_by_install_pyenv_fix_37648():
    """
    Guard against overcorrection of the fix for issue #37648: the sibling
    pyenv.installed state must still install a missing python version via
    pyenv.install_python, with ``user`` passed as ``runas``. This test is
    expected to pass both with and without the install_pyenv fix.
    """
    name = "python-2.7.6"
    user = "pyenv_user"

    mock_is = MagicMock(return_value=True)
    mock_ip = MagicMock(return_value=True)
    mock_d = MagicMock(return_value="")
    mock_v = MagicMock(return_value=[])
    with patch.dict(
        pyenv.__salt__,
        {
            "pyenv.is_installed": mock_is,
            "pyenv.install_python": mock_ip,
            "pyenv.default": mock_d,
            "pyenv.versions": mock_v,
        },
    ), patch.dict(pyenv.__opts__, {"test": False}):
        ret = pyenv.installed(name, user=user)

    assert ret == {
        "name": name,
        "changes": {"2.7.6": "Installed"},
        "result": True,
        "comment": "Successfully installed python",
        "default": False,
    }
    mock_ip.assert_called_once_with("2.7.6", runas=user)
