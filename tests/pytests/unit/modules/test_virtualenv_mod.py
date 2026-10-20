"""
Tests for salt.modules.virtualenv_mod
"""

import logging
import sys

import pytest

import salt.modules.virtualenv_mod as virtualenv_mod
from salt.exceptions import CommandExecutionError
from tests.support.helpers import ForceImportErrorOn
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    base_virtualenv_mock = MagicMock()
    base_virtualenv_mock.__version__ = "1.9.1"
    return {
        virtualenv_mod: {
            "__opts__": {"venv_bin": "virtualenv"},
            "_install_script": MagicMock(
                return_value={
                    "retcode": 0,
                    "stdout": "Installed script!",
                    "stderr": "",
                }
            ),
            "sys.modules": {"virtualenv": base_virtualenv_mock},
        }
    }


@pytest.fixture(autouse=True)
def which_identity():
    # The interpreter/python lookups performed by create() must find whatever
    # binary name the tests pass in.
    with patch("salt.utils.path.which", lambda exe: exe):
        yield


def test_issue_6029_deprecated_distribute(caplog):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", system_site_packages=True, distribute=True)
        mock.assert_called_once_with(
            ["virtualenv", "--distribute", "--system-site-packages", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )

    with caplog.at_level(logging.INFO, logger="salt.modules.virtualenv_mod"):
        # Let's fake a higher virtualenv version
        virtualenv_mock = MagicMock()
        virtualenv_mock.__version__ = "1.10rc1"
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            with patch.dict("sys.modules", {"virtualenv": virtualenv_mock}):
                virtualenv_mod.create(
                    "/tmp/foo", system_site_packages=True, distribute=True
                )
                mock.assert_called_once_with(
                    ["virtualenv", "--system-site-packages", "/tmp/foo"],
                    runas=None,
                    python_shell=False,
                )

            # Are we logging the deprecation information?
            assert (
                "The virtualenv '--distribute' option has been "
                "deprecated in virtualenv(>=1.10), as such, the "
                "'distribute' option to `virtualenv.create()` has "
                "also been deprecated and it's not necessary anymore."
                in caplog.messages
            )


def test_issue_6030_deprecated_never_download(caplog):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", never_download=True)
        mock.assert_called_once_with(
            ["virtualenv", "--never-download", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )

    with caplog.at_level(logging.INFO, logger="salt.modules.virtualenv_mod"):
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        # Let's fake a higher virtualenv version
        virtualenv_mock = MagicMock()
        virtualenv_mock.__version__ = "1.10rc1"
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            with patch.dict("sys.modules", {"virtualenv": virtualenv_mock}):
                virtualenv_mod.create("/tmp/foo", never_download=True)
                mock.assert_called_once_with(
                    ["virtualenv", "/tmp/foo"], runas=None, python_shell=False
                )

            # Are we logging the deprecation information?
            assert (
                "--never-download was deprecated in 1.10.0, "
                "but reimplemented in 14.0.0. If this feature is needed, "
                "please install a supported virtualenv version." in caplog.messages
            )


@pytest.mark.parametrize(
    "extra_search_dir",
    [
        ["/tmp/bar-1", "/tmp/bar-2", "/tmp/bar-3"],
        "/tmp/bar-1,/tmp/bar-2,/tmp/bar-3",
    ],
    ids=["list", "comma-separated-string"],
)
def test_issue_6031_multiple_extra_search_dirs(extra_search_dir):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", extra_search_dir=extra_search_dir)
        mock.assert_called_once_with(
            [
                "virtualenv",
                "--extra-search-dir=/tmp/bar-1",
                "--extra-search-dir=/tmp/bar-2",
                "--extra-search-dir=/tmp/bar-3",
                "/tmp/foo",
            ],
            runas=None,
            python_shell=False,
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"venv_bin": "virtualenv", "upgrade": True},
        {"venv_bin": "virtualenv", "symlinks": True},
        {"venv_bin": "pyvenv", "python": "python2.7"},
        {"venv_bin": "pyvenv", "never_download": True},
        {"venv_bin": "pyvenv", "extra_search_dir": "/tmp/bar"},
    ],
    ids=[
        "virtualenv-upgrade",
        "virtualenv-symlinks",
        "pyvenv-python",
        "pyvenv-never_download",
        "pyvenv-extra_search_dir",
    ],
)
def test_unapplicable_options(kwargs):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            virtualenv_mod.create("/tmp/foo", **kwargs)


def test_pyvenv_accepts_prompt():
    # Historically the prompt option was rejected on the venv code path, but
    # the venv module has supported --prompt since Python 3.6.
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="pyvenv", prompt="PY Prompt")
        mock.assert_called_once_with(
            ["pyvenv", "--prompt", "PY Prompt", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_get_virtualenv_version_from_shell():
    with ForceImportErrorOn("virtualenv"):

        # ----- virtualenv binary not available ------------------------->
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            with pytest.raises(CommandExecutionError):
                virtualenv_mod.create("/tmp/foo")
        # <---- virtualenv binary not available --------------------------

        # ----- virtualenv binary present but > 0 exit code ------------->
        mock = MagicMock(
            side_effect=[
                {"retcode": 1, "stdout": "", "stderr": "This is an error"},
                {"retcode": 0, "stdout": ""},
            ]
        )
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            with pytest.raises(CommandExecutionError):
                virtualenv_mod.create("/tmp/foo", venv_bin="virtualenv")
        # <---- virtualenv binary present but > 0 exit code --------------

        # ----- virtualenv binary returns 1.9.1 as its version --------->
        mock = MagicMock(
            side_effect=[
                {"retcode": 0, "stdout": "1.9.1"},
                {"retcode": 0, "stdout": ""},
            ]
        )
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            virtualenv_mod.create("/tmp/foo", never_download=True)
            mock.assert_called_with(
                ["virtualenv", "--never-download", "/tmp/foo"],
                runas=None,
                python_shell=False,
            )
        # <---- virtualenv binary returns 1.9.1 as its version ----------

        # ----- virtualenv binary returns 1.10rc1 as its version ------->
        mock = MagicMock(
            side_effect=[
                {"retcode": 0, "stdout": "1.10rc1"},
                {"retcode": 0, "stdout": ""},
            ]
        )
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
            virtualenv_mod.create("/tmp/foo", never_download=True)
            mock.assert_called_with(
                ["virtualenv", "/tmp/foo"], runas=None, python_shell=False
            )
        # <---- virtualenv binary returns 1.10rc1 as its version --------


def test_python_argument():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", python=sys.executable)
        mock.assert_called_once_with(
            ["virtualenv", f"--python={sys.executable}", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("PY Prompt", "--prompt='PY Prompt'"),
        ("'PY' Prompt", "--prompt=''PY' Prompt'"),
        ('"PY" Prompt', "--prompt='\"PY\" Prompt'"),
    ],
    ids=["plain", "single-quotes", "double-quotes"],
)
def test_prompt_argument(prompt, expected):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", prompt=prompt)
        mock.assert_called_once_with(
            ["virtualenv", expected, "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_clear_argument():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", clear=True)
        mock.assert_called_once_with(
            ["virtualenv", "--clear", "/tmp/foo"], runas=None, python_shell=False
        )


def test_upgrade_argument():
    # We test for pyvenv only because with virtualenv this is an
    # unsupported option.
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="pyvenv", upgrade=True)
        mock.assert_called_once_with(
            ["pyvenv", "--upgrade", "/tmp/foo"], runas=None, python_shell=False
        )


def test_symlinks_argument():
    # We test for pyvenv only because with virtualenv this is an
    # unsupported option.
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="pyvenv", symlinks=True)
        mock.assert_called_once_with(
            ["pyvenv", "--symlinks", "/tmp/foo"], runas=None, python_shell=False
        )


def test_virtualenv_ver():
    """
    test virtualenv_ver when there is no ImportError
    """
    ret = virtualenv_mod.virtualenv_ver(venv_bin="pyvenv")
    assert ret == (1, 9, 1)


def test_virtualenv_ver_importerror():
    """
    test virtualenv_ver when there is an ImportError
    """
    with ForceImportErrorOn("virtualenv"):
        mock_ver = MagicMock(return_value={"retcode": 0, "stdout": "1.9.1"})
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock_ver}):
            ret = virtualenv_mod.virtualenv_ver(venv_bin="pyenv")
    assert ret == (1, 9, 1)


def test_virtualenv_ver_importerror_cmd_error():
    """
    test virtualenv_ver when there is an ImportError
    and virtualenv --version does not return anything
    """
    with ForceImportErrorOn("virtualenv"):
        mock_ver = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock_ver}):
            with pytest.raises(CommandExecutionError):
                virtualenv_mod.virtualenv_ver(venv_bin="pyenv")


@pytest.mark.parametrize(
    "stdout,expected",
    [
        ("1.9.2", (1, 9, 2)),
        ("1.9rc2", (1, 9)),
        (
            "virtualenv 20.0.0 from"
            " /home/ch3ll/.pyenv/versions/3.6.4/envs/virtualenv/lib/python3.6/site-packages/virtualenv/__init__.py",
            (20, 0, 0),
        ),
        ("16.7.10", (16, 7, 10)),
    ],
)
def test_virtualenv_importerror_ver_output(stdout, expected):
    """
    test virtualenv_ver when there is an ImportError
    and virtualenv --version returns the various
    --versions outputs
    """
    with ForceImportErrorOn("virtualenv"):
        mock_ver = MagicMock(return_value={"retcode": 0, "stdout": stdout})
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock_ver}):
            ret = virtualenv_mod.virtualenv_ver(venv_bin="pyenv")
            assert ret == expected


def test_issue_57734_debian_package():
    virtualenv_mock = MagicMock()
    virtualenv_mock.__version__ = "20.0.23+ds"
    with patch.dict("sys.modules", {"virtualenv": virtualenv_mock}):
        ret = virtualenv_mod.virtualenv_ver(venv_bin="pyenv")
    assert ret == (20, 0, 23)


def test_issue_57734_debian_package_importerror():
    with ForceImportErrorOn("virtualenv"):
        mock_ver = MagicMock(
            return_value={
                "retcode": 0,
                "stdout": (
                    "virtualenv 20.0.23+ds from "
                    "/usr/lib/python3/dist-packages/virtualenv/__init__.py"
                ),
            }
        )
        with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock_ver}):
            ret = virtualenv_mod.virtualenv_ver(venv_bin="pyenv")
    assert ret == (20, 0, 23)


def test_venv_module_default_interpreter():
    """
    venv_bin=venv runs the venv module with the interpreter running the minion
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="venv")
        mock.assert_called_once_with(
            [sys.executable, "-m", "venv", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_venv_module_with_python():
    """
    venv_bin=venv with python selects the interpreter that runs -m venv
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="venv", python="python3.11")
        mock.assert_called_once_with(
            ["python3.11", "-m", "venv", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_venv_module_python_not_found():
    """
    venv_bin=venv with a python that cannot be found raises an error
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with patch("salt.utils.path.which", MagicMock(return_value=None)):
            with pytest.raises(CommandExecutionError):
                virtualenv_mod.create("/tmp/foo", venv_bin="venv", python="python3.11")
    mock.assert_not_called()


def test_interpreter_as_venv_bin():
    """
    A python interpreter passed as venv_bin runs <interpreter> -m venv
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="/usr/bin/python3.11")
        mock.assert_called_once_with(
            ["/usr/bin/python3.11", "-m", "venv", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_interpreter_as_venv_bin_with_python_is_ambiguous():
    """
    Passing an interpreter as venv_bin AND a python is rejected as ambiguous
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            virtualenv_mod.create(
                "/tmp/foo", venv_bin="/usr/bin/python3.11", python="python3.9"
            )
    mock.assert_not_called()


def test_interpreter_as_venv_bin_not_found():
    """
    An interpreter passed as venv_bin that cannot be found raises an error
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with patch("salt.utils.path.which", MagicMock(return_value=None)):
            with pytest.raises(CommandExecutionError):
                virtualenv_mod.create("/tmp/foo", venv_bin="/usr/bin/python3.11")
    mock.assert_not_called()


def test_venv_module_prompt():
    """
    venv_bin=venv passes --prompt through to the venv module
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="venv", prompt="My Env")
        mock.assert_called_once_with(
            [sys.executable, "-m", "venv", "--prompt", "My Env", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )


def test_venv_module_option_ordering():
    """
    venv module options are appended in a stable order
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create(
            "/tmp/foo",
            venv_bin="venv",
            upgrade=True,
            symlinks=True,
            clear=True,
            system_site_packages=True,
        )
        mock.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "venv",
                "--upgrade",
                "--symlinks",
                "--clear",
                "--system-site-packages",
                "/tmp/foo",
            ],
            runas=None,
            python_shell=False,
        )


def test_pyvenv_python_still_rejected():
    """
    A non-interpreter venv-style binary (pyvenv) still rejects the python option
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            virtualenv_mod.create("/tmp/foo", venv_bin="pyvenv", python="python3")
    mock.assert_not_called()


@pytest.mark.parametrize(
    "venv_bin,expected",
    [
        ("python", True),
        ("python3", True),
        ("python3.11", True),
        ("/usr/bin/python3.10", True),
        ("python.exe", True),
        pytest.param(
            "C:\\Python311\\python.exe",
            True,
            marks=pytest.mark.skip_unless_on_windows(
                reason="os.path.basename() only splits on backslashes on Windows"
            ),
        ),
        ("pypy3", True),
        ("pypy", True),
        ("virtualenv", False),
        ("pyvenv", False),
        ("python-config", False),
        ("/opt/venvs/virtualenv", False),
        ("mypython3", False),
    ],
)
def test_is_python_binary(venv_bin, expected):
    assert virtualenv_mod._is_python_binary(venv_bin) is expected


def test_venv_failure_removes_partial_env(tmp_path):
    """
    A failed creation removes the partially created environment, so a later
    run (or virtualenv.managed, which keys existence off bin/python) does
    not mistake it for a working one.
    """
    env_dir = tmp_path / "env"

    def failing_run_all(cmd, **kwargs):
        (env_dir / "bin").mkdir(parents=True)
        (env_dir / "bin" / "python").touch()
        return {"retcode": 1, "stdout": "", "stderr": "ensurepip is not available"}

    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": failing_run_all}):
        ret = virtualenv_mod.create(str(env_dir), venv_bin="venv")
    assert ret["retcode"] == 1
    assert not env_dir.exists()


def test_venv_failure_keeps_preexisting_path(tmp_path):
    """
    The failure cleanup never removes a path that already existed before the
    creation command ran.
    """
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    marker = env_dir / "precious"
    marker.touch()

    mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "boom"})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        ret = virtualenv_mod.create(str(env_dir), venv_bin="venv", clear=True)
    assert ret["retcode"] == 1
    assert marker.exists()


def test_venv_extra_search_dir_list_rejected():
    """
    A list-valued extra_search_dir is rejected cleanly on the venv path
    instead of raising AttributeError on list.strip().
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            virtualenv_mod.create(
                "/tmp/foo",
                venv_bin="venv",
                python="python3.11",
                extra_search_dir=["/tmp/bar"],
            )
    mock.assert_not_called()


def test_venv_skips_setuptools_bootstrap():
    """
    venv-module environments never get the obsolete easy_install/ez_setup
    bootstrap; ensurepip already provides pip there.
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "", "stderr": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}):
        virtualenv_mod.create("/tmp/foo", venv_bin="venv", pip=True)
    ez_setup_calls = [
        call
        for call in virtualenv_mod._install_script.call_args_list
        if "ez_setup" in call[0][0]
    ]
    assert not ez_setup_calls


def test_default_resolution_pillar_overrides_opts():
    """
    With venv_bin unset, the pillar value wins over the minion config value.
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(virtualenv_mod.__salt__, {"cmd.run_all": mock}), patch.dict(
        virtualenv_mod.__pillar__, {"venv_bin": "venv"}
    ):
        virtualenv_mod.create("/tmp/foo")
        mock.assert_called_once_with(
            [sys.executable, "-m", "venv", "/tmp/foo"],
            runas=None,
            python_shell=False,
        )
