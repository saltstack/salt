import os
import sys
from textwrap import dedent

import pytest

import salt.modules.pip as pip
import salt.utils.files
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

TARGET = []
if os.environ.get("VENV_PIP_TARGET"):
    TARGET = ["--target", os.environ.get("VENV_PIP_TARGET")]


class FakeFopen:
    def __init__(self, filename):
        d = {
            "requirements-0.txt": (
                b"--index-url http://fake.com/simple\n\n"
                b"one  # -r wrong.txt, other\n"
                b"two # --requirement wrong.exe;some\n"
                b"three\n"
                b"-r requirements-1.txt\n"
                b"# nothing\n"
            ),
            "requirements-1.txt": (
                "four\n"
                "five\n"
                "--requirement=requirements-2.txt\t# --requirements-2.txt\n\n"
            ),
            "requirements-2.txt": b"""six""",
            "requirements-3.txt": (
                b"# some comment\n"
                b"-e git+ssh://git.example.com/MyProject#egg=MyProject # the project\n"
                b"seven\n"
                b"-e git+ssh://git.example.com/Example#egg=example\n"
                b"eight # -e something#or other\n"
                b"--requirement requirements-4.txt\n\n"
            ),
            "requirements-4.txt": "",
        }
        self.val = d[filename]

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def read(self):
        return self.val


@pytest.fixture
def expected_user():
    return "fnord"


@pytest.fixture
def configure_loader_modules():
    return {pip: {"__salt__": {"cmd.which_bin": lambda _: "pip"}}}


def test__pip_bin_env():
    ret = pip._pip_bin_env(None, "C:/Users/ch44d/Documents/salt/tests/pip.exe")
    if salt.utils.platform.is_windows():
        assert ret == "C:/Users/ch44d/Documents/salt/tests"
    else:
        assert ret is None


def test__pip_bin_env_no_change():
    cwd = "C:/Users/ch44d/Desktop"
    ret = pip._pip_bin_env(cwd, "C:/Users/ch44d/Documents/salt/tests/pip.exe")
    assert ret == cwd


def test__pip_bin_env_no_bin_env():
    ret = pip._pip_bin_env(None, None)
    assert ret is None


@pytest.fixture
def python_binary():
    binary = [sys.executable, "-m", "pip"]
    if hasattr(sys, "RELENV"):
        binary = [str(sys.RELENV / "salt-pip")]
    return binary


def test_install_frozen_app(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch("sys.frozen", True, create=True):
        with patch("sys._MEIPASS", True, create=True):
            with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
                pip.install(pkg)
                expected = [
                    *python_binary,
                    "install",
                    *TARGET,
                    pkg,
                ]
                mock.assert_called_with(
                    expected,
                    python_shell=False,
                    saltenv="base",
                    use_vt=False,
                    runas=None,
                )


def test_install_source_app(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch("sys.frozen", False, create=True):
        with patch("sys._MEIPASS", False, create=True):
            with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
                pip.install(pkg)
                expected = [
                    *python_binary,
                    "install",
                    *TARGET,
                    pkg,
                ]
                mock.assert_called_with(
                    expected,
                    python_shell=False,
                    saltenv="base",
                    use_vt=False,
                    runas=None,
                )


def test_fix4361(python_binary):
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(requirements="requirements.txt")
        expected_cmd = [
            *python_binary,
            "install",
            "--requirement",
            "requirements.txt",
            *TARGET,
        ]
        mock.assert_called_with(
            expected_cmd,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_editable_without_egg_fails():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError,
            pip.install,
            editable="git+https://github.com/saltstack/salt-testing.git",
        )


def test_install_multiple_editable(python_binary):
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]

    expected = [*python_binary, "install", *TARGET]
    for item in editables:
        expected.extend(["--editable", item])

    # Passing editables as a list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(editable=editables)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing editables as a comma separated list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(editable=",".join(editables))
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_multiple_pkgs_and_editables(python_binary):
    pkgs = ["pep8", "salt"]
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]

    expected = [*python_binary, "install", *TARGET]
    expected.extend(pkgs)
    for item in editables:
        expected.extend(["--editable", item])

    # Passing editables as a list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkgs=pkgs, editable=editables)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing editables as a comma separated list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkgs=",".join(pkgs), editable=",".join(editables))
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # As single string (just use the first element from pkgs and editables)
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkgs=pkgs[0], editable=editables[0])
        expected = [
            *python_binary,
            "install",
            *TARGET,
            pkgs[0],
            "--editable",
            editables[0],
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_issue5940_install_multiple_pip_mirrors(python_binary):
    """
    test multiple pip mirrors.  This test only works with pip < 7.0.0
    """
    with patch.object(pip, "version", MagicMock(return_value="1.4")):
        mirrors = [
            "http://g.pypi.python.org",
            "http://c.pypi.python.org",
            "http://pypi.crate.io",
        ]

        expected = [*python_binary, "install", "--use-mirrors"]
        for item in mirrors:
            expected.extend(["--mirrors", item])
        expected = [*expected, *TARGET, "pep8"]

        # Passing mirrors as a list
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(pkgs=["pep8"], mirrors=mirrors)
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing mirrors as a comma separated list
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(pkgs=["pep8"], mirrors=",".join(mirrors))
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        expected = [
            *python_binary,
            "install",
            "--use-mirrors",
            "--mirrors",
            mirrors[0],
            *TARGET,
            "pep8",
        ]

        # As single string (just use the first element from mirrors)
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(pkgs=["pep8"], mirrors=mirrors[0])
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_with_multiple_find_links(python_binary):
    find_links = [
        "http://g.pypi.python.org",
        "http://c.pypi.python.org",
        "http://pypi.crate.io",
    ]
    pkg = "pep8"

    expected = [*python_binary, "install"]
    for item in find_links:
        expected.extend(["--find-links", item])
    expected = [*expected, *TARGET, pkg]

    # Passing mirrors as a list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, find_links=find_links)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing mirrors as a comma separated list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, find_links=",".join(find_links))
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Valid protos work?
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, find_links=find_links)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    expected = [
        *python_binary,
        "install",
        "--find-links",
        find_links[0],
        *TARGET,
        pkg,
    ]

    # As single string (just use the first element from find_links)
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, find_links=find_links[0])
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Invalid proto raises exception
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError,
            pip.install,
            "'" + pkg + "'",
            find_links="sftp://pypi.crate.io",
        )


def test_install_no_index_with_index_url_or_extra_index_url_raises():
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError,
            pip.install,
            no_index=True,
            index_url="http://foo.tld",
        )

    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            CommandExecutionError,
            pip.install,
            no_index=True,
            extra_index_url="http://foo.tld",
        )


def test_install_failed_cached_requirements():
    with patch("salt.modules.pip._get_cached_requirements") as get_cached_requirements:
        get_cached_requirements.return_value = False
        ret = pip.install(requirements="salt://my_test_reqs")
        assert False is ret["result"]
        assert "my_test_reqs" in ret["comment"]


def test_install_cached_requirements_used(python_binary):
    with patch("salt.modules.pip._get_cached_requirements") as get_cached_requirements:
        get_cached_requirements.return_value = "my_cached_reqs"
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(requirements="salt://requirements.txt")
            expected = [
                *python_binary,
                "install",
                "--requirement",
                "my_cached_reqs",
                *TARGET,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_venv():
    with patch("os.path") as mock_path:

        def join(*args):
            return os.path.normpath(os.sep.join(args))

        mock_path.is_file.return_value = True
        mock_path.isdir.return_value = True
        mock_path.join = join

        if salt.utils.platform.is_windows():
            venv_path = "C:\\test_env"
            bin_path = os.path.join(venv_path, "python.exe")
        else:
            venv_path = "/test_env"
            bin_path = os.path.join(venv_path, "python")

        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        pip_bin = MagicMock(return_value=[bin_path, "-m", "pip"])

        with patch.dict(pip.__salt__, {"cmd.run_all": mock}), patch.object(
            pip, "_get_pip_bin", pip_bin
        ):
            pip.install("mock", bin_env=venv_path)
            mock.assert_called_with(
                [bin_path, "-m", "pip", "install", "mock"],
                env={"VIRTUAL_ENV": venv_path},
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_log_argument_in_resulting_command(python_binary, tmp_path):
    with patch("os.access") as mock_path:
        pkg = "pep8"
        log_path = str(tmp_path / "pip-install.log")
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(pkg, log=log_path)
            expected = [
                *python_binary,
                "install",
                "--log",
                log_path,
                *TARGET,
                pkg,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_non_writeable_log():
    with patch("os.path") as mock_path:
        # Let's fake a non-writable log file
        pkg = "pep8"
        log_path = "/tmp/pip-install.log"
        mock_path.exists.side_effect = IOError("Fooo!")
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pytest.raises(IOError, pip.install, pkg, log=log_path)


def test_install_timeout_argument_in_resulting_command(python_binary):
    # Passing an int
    pkg = "pep8"
    expected = [*python_binary, "install", "--timeout"]
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, timeout=10)
        mock.assert_called_with(
            expected + [10, *TARGET, pkg],
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing an int as a string
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, timeout="10")
        mock.assert_called_with(
            expected + ["10", *TARGET, pkg],
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing a non-int to timeout
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(ValueError, pip.install, pkg, timeout="a")


def test_install_index_url_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    index_url = "http://foo.tld"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, index_url=index_url)
        expected = [
            *python_binary,
            "install",
            "--index-url",
            index_url,
            *TARGET,
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_extra_index_url_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    extra_index_url = "http://foo.tld"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, extra_index_url=extra_index_url)
        expected = [
            *python_binary,
            "install",
            "--extra-index-url",
            extra_index_url,
            *TARGET,
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_no_index_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, no_index=True)
        expected = [*python_binary, "install", "--no-index", *TARGET, pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_build_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    build = "/tmp/foo"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, build=build)
        expected = [*python_binary, "install", "--build", build, *TARGET, pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_target_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    target = "/tmp/foo"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, target=target)
        expected = [*python_binary, "install", "--target", target, pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_download_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    download = "/tmp/foo"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, download=download)
        expected = [
            *python_binary,
            "install",
            *TARGET,
            "--download",
            download,
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_no_download_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, no_download=True)
        expected = [*python_binary, "install", *TARGET, "--no-download", pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_download_cache_dir_arguments_in_resulting_command(python_binary):
    pkg = "pep8"
    cache_dir_arg_mapping = {
        "1.5.6": "--download-cache",
        "6.0": "--cache-dir",
    }
    download_cache = "/tmp/foo"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})

    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        for pip_version, cmd_arg in cache_dir_arg_mapping.items():
            with patch("salt.modules.pip.version", MagicMock(return_value=pip_version)):
                # test `download_cache` kwarg
                pip.install(pkg, download_cache="/tmp/foo")
                expected = [
                    *python_binary,
                    "install",
                    *TARGET,
                    cmd_arg,
                    download_cache,
                    pkg,
                ]
                mock.assert_called_with(
                    expected,
                    saltenv="base",
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )

                # test `cache_dir` kwarg
                pip.install(pkg, cache_dir="/tmp/foo")
                mock.assert_called_with(
                    expected,
                    saltenv="base",
                    runas=None,
                    use_vt=False,
                    python_shell=False,
                )


def test_install_source_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    source = "/tmp/foo"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, source=source)
        expected = [*python_binary, "install", *TARGET, "--source", source, pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_exists_action_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    for action in ("s", "i", "w", "b"):
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(pkg, exists_action=action)
            expected = [
                *python_binary,
                "install",
                *TARGET,
                "--exists-action",
                action,
                pkg,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    # Test for invalid action
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(CommandExecutionError, pip.install, pkg, exists_action="d")


def test_install_install_options_argument_in_resulting_command(python_binary):
    install_options = ["--exec-prefix=/foo/bar", "--install-scripts=/foo/bar/bin"]
    pkg = "pep8"

    expected = [*python_binary, "install", *TARGET]
    for item in install_options:
        expected.extend(["--install-option", item])
    expected.append(pkg)

    # Passing options as a list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, install_options=install_options)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing mirrors as a comma separated list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, install_options=",".join(install_options))
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing mirrors as a single string entry
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, install_options=install_options[0])
        expected = [
            *python_binary,
            "install",
            *TARGET,
            "--install-option",
            install_options[0],
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_global_options_argument_in_resulting_command(python_binary):
    global_options = ["--quiet", "--no-user-cfg"]
    pkg = "pep8"

    expected = [*python_binary, "install", *TARGET]
    for item in global_options:
        expected.extend(["--global-option", item])
    expected.append(pkg)

    # Passing options as a list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, global_options=global_options)
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing mirrors as a comma separated list
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, global_options=",".join(global_options))
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing mirrors as a single string entry
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, global_options=global_options[0])
        expected = [
            *python_binary,
            "install",
            *TARGET,
            "--global-option",
            global_options[0],
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_upgrade_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, upgrade=True)
        expected = [*python_binary, "install", *TARGET, "--upgrade", pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_force_reinstall_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, force_reinstall=True)
        expected = [
            *python_binary,
            "install",
            *TARGET,
            "--force-reinstall",
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_ignore_installed_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, ignore_installed=True)
        expected = [
            *python_binary,
            "install",
            *TARGET,
            "--ignore-installed",
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_no_deps_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, no_deps=True)
        expected = [*python_binary, "install", *TARGET, "--no-deps", pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_no_install_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, no_install=True)
        expected = [*python_binary, "install", *TARGET, "--no-install", pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_proxy_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    proxy = "salt-user:salt-passwd@salt-proxy:3128"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(pkg, proxy=proxy)
        expected = [*python_binary, "install", "--proxy", proxy, *TARGET, pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_proxy_false_argument_in_resulting_command(python_binary):
    """
    Checking that there is no proxy set if proxy arg is set to False
    even if the global proxy is set.
    """
    pkg = "pep8"
    proxy = False
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    config_mock = {
        "proxy_host": "salt-proxy",
        "proxy_port": "3128",
        "proxy_username": "salt-user",
        "proxy_password": "salt-passwd",
    }
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch.dict(pip.__opts__, config_mock):
            pip.install(pkg, proxy=proxy)
            expected = [*python_binary, "install", *TARGET, pkg]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_global_proxy_in_resulting_command(python_binary):
    """
    Checking that there is proxy set if global proxy is set.
    """
    pkg = "pep8"
    proxy = "http://salt-user:salt-passwd@salt-proxy:3128"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    config_mock = {
        "proxy_host": "salt-proxy",
        "proxy_port": "3128",
        "proxy_username": "salt-user",
        "proxy_password": "salt-passwd",
    }
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch.dict(pip.__opts__, config_mock):
            pip.install(pkg)
            expected = [
                *python_binary,
                "install",
                "--proxy",
                proxy,
                *TARGET,
                pkg,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_multiple_requirements_arguments_in_resulting_command(python_binary):
    with patch("salt.modules.pip._get_cached_requirements") as get_cached_requirements:
        cached_reqs = ["my_cached_reqs-1", "my_cached_reqs-2"]
        get_cached_requirements.side_effect = cached_reqs
        requirements = ["salt://requirements-1.txt", "salt://requirements-2.txt"]

        expected = [*python_binary, "install"]
        for item in cached_reqs:
            expected.extend(["--requirement", item])
        expected.extend(TARGET)

        # Passing option as a list
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(requirements=requirements)
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a comma separated list
        get_cached_requirements.side_effect = cached_reqs
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(requirements=",".join(requirements))
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a single string entry
        get_cached_requirements.side_effect = [cached_reqs[0]]
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.install(requirements=requirements[0])
            expected = [
                *python_binary,
                "install",
                "--requirement",
                cached_reqs[0],
                *TARGET,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_install_extra_args_arguments_in_resulting_command(python_binary):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.install(
            pkg, extra_args=[{"--latest-pip-kwarg": "param"}, "--latest-pip-arg"]
        )
        expected = [
            *python_binary,
            "install",
            *TARGET,
            pkg,
            "--latest-pip-kwarg",
            "param",
            "--latest-pip-arg",
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_install_extra_args_arguments_recursion_error():
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(
            TypeError,
            lambda: pip.install(
                pkg, extra_args=[{"--latest-pip-kwarg": ["param1", "param2"]}]
            ),
        )

        pytest.raises(
            TypeError,
            lambda: pip.install(
                pkg, extra_args=[{"--latest-pip-kwarg": [{"--too-deep": dict()}]}]
            ),
        )


def test_uninstall_multiple_requirements_arguments_in_resulting_command(python_binary):
    with patch("salt.modules.pip._get_cached_requirements") as get_cached_requirements:
        cached_reqs = ["my_cached_reqs-1", "my_cached_reqs-2"]
        get_cached_requirements.side_effect = cached_reqs
        requirements = ["salt://requirements-1.txt", "salt://requirements-2.txt"]

        expected = [*python_binary, "uninstall", "-y"]
        for item in cached_reqs:
            expected.extend(["--requirement", item])

        # Passing option as a list
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.uninstall(requirements=requirements)
            mock.assert_called_with(
                expected,
                cwd=None,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a comma separated list
        get_cached_requirements.side_effect = cached_reqs
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.uninstall(requirements=",".join(requirements))
            mock.assert_called_with(
                expected,
                cwd=None,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

        # Passing option as a single string entry
        get_cached_requirements.side_effect = [cached_reqs[0]]
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pip.uninstall(requirements=requirements[0])
            expected = [
                *python_binary,
                "uninstall",
                "-y",
                "--requirement",
                cached_reqs[0],
            ]
            mock.assert_called_with(
                expected,
                cwd=None,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_uninstall_global_proxy_in_resulting_command(python_binary):
    """
    Checking that there is proxy set if global proxy is set.
    """
    pkg = "pep8"
    proxy = "http://salt-user:salt-passwd@salt-proxy:3128"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    config_mock = {
        "proxy_host": "salt-proxy",
        "proxy_port": "3128",
        "proxy_username": "salt-user",
        "proxy_password": "salt-passwd",
    }
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch.dict(pip.__opts__, config_mock):
            pip.uninstall(pkg)
            expected = [
                *python_binary,
                "uninstall",
                "-y",
                "--proxy",
                proxy,
                pkg,
            ]
            mock.assert_called_with(
                expected,
                saltenv="base",
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_uninstall_proxy_false_argument_in_resulting_command(python_binary):
    """
    Checking that there is no proxy set if proxy arg is set to False
    even if the global proxy is set.
    """
    pkg = "pep8"
    proxy = False
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    config_mock = {
        "proxy_host": "salt-proxy",
        "proxy_port": "3128",
        "proxy_username": "salt-user",
        "proxy_password": "salt-passwd",
    }
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch.dict(pip.__opts__, config_mock):
            pip.uninstall(pkg, proxy=proxy)
            expected = [*python_binary, "uninstall", "-y", pkg]
            mock.assert_called_with(
                expected,
                saltenv="base",
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_uninstall_log_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    log_path = "/tmp/pip-install.log"

    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.uninstall(pkg, log=log_path)
        expected = [
            *python_binary,
            "uninstall",
            "-y",
            "--log",
            log_path,
            pkg,
        ]
        mock.assert_called_with(
            expected,
            saltenv="base",
            cwd=None,
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Let's fake a non-writable log file
    with patch("os.path") as mock_path:
        mock_path.exists.side_effect = IOError("Fooo!")
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
            pytest.raises(IOError, pip.uninstall, pkg, log=log_path)


def test_uninstall_timeout_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    expected = [*python_binary, "uninstall", "-y", "--timeout"]
    # Passing an int
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.uninstall(pkg, timeout=10)
        mock.assert_called_with(
            expected + [10, pkg],
            cwd=None,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing an int as a string
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pip.uninstall(pkg, timeout="10")
        mock.assert_called_with(
            expected + ["10", pkg],
            cwd=None,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )

    # Passing a non-int to timeout
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        pytest.raises(ValueError, pip.uninstall, pkg, timeout="a")


def test_freeze_command(python_binary):
    expected = [*python_binary, "freeze"]
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pycrypto==2.6",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.freeze()
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
            )
            assert ret == eggs

    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    # Passing env_vars passes them to underlying command?
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.freeze(env_vars={"foo": "bar"})
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
                env={"foo": "bar"},
            )
            assert ret == eggs

    # Non zero returncode raises exception?
    mock = MagicMock(return_value={"retcode": 1, "stderr": "CABOOOOMMM!"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            pytest.raises(
                CommandExecutionError,
                pip.freeze,
            )


def test_freeze_command_with_all(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pip==0.9.1",
        "pycrypto==2.6",
        "setuptools==20.10.1",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="9.0.1")):
            ret = pip.freeze()
            expected = [*python_binary, "freeze", "--all"]
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                use_vt=False,
                python_shell=False,
            )
            assert ret == eggs

    # Non zero returncode raises exception?
    mock = MagicMock(return_value={"retcode": 1, "stderr": "CABOOOOMMM!"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="9.0.1")):
            pytest.raises(
                CommandExecutionError,
                pip.freeze,
            )


def test_list_freeze_parse_command(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pycrypto==2.6",
    ]
    mock_version = "6.1.1"
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value=mock_version)):
            ret = pip.list_freeze_parse()
            expected = [*python_binary, "freeze"]
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                python_shell=False,
                use_vt=False,
            )
            assert ret == {
                "SaltTesting-dev": "git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8",
                "M2Crypto": "0.21.1",
                "bbfreeze-loader": "1.1.0",
                "bbfreeze": "1.1.0",
                "pip": mock_version,
                "pycrypto": "2.6",
            }

    # Non zero returncode raises exception?
    mock = MagicMock(return_value={"retcode": 1, "stderr": "CABOOOOMMM!"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            pytest.raises(
                CommandExecutionError,
                pip.list_freeze_parse,
            )


def test_list_freeze_parse_command_with_all(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pip==9.0.1",
        "pycrypto==2.6",
        "setuptools==20.10.1",
    ]
    # N.B.: this is deliberately different from the "output" of pip freeze.
    # This is to demonstrate that the version reported comes from freeze
    # instead of from the pip.version function.
    mock_version = "9.0.0"
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value=mock_version)):
            ret = pip.list_freeze_parse()
            expected = [*python_binary, "freeze", "--all"]
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                python_shell=False,
                use_vt=False,
            )
            assert ret == {
                "SaltTesting-dev": "git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8",
                "M2Crypto": "0.21.1",
                "bbfreeze-loader": "1.1.0",
                "bbfreeze": "1.1.0",
                "pip": "9.0.1",
                "pycrypto": "2.6",
                "setuptools": "20.10.1",
            }

    # Non zero returncode raises exception?
    mock = MagicMock(return_value={"retcode": 1, "stderr": "CABOOOOMMM!"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            pytest.raises(
                CommandExecutionError,
                pip.list_freeze_parse,
            )


def test_list_freeze_parse_command_with_prefix(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pycrypto==2.6",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.list_freeze_parse(prefix="bb")
            expected = [*python_binary, "freeze"]
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                python_shell=False,
                use_vt=False,
            )
            assert ret == {"bbfreeze-loader": "1.1.0", "bbfreeze": "1.1.0"}


def test_list_upgrades_legacy(python_binary):
    eggs = [
        "apache-libcloud (Current: 1.1.0 Latest: 2.2.1 [wheel])",
        "appdirs (Current: 1.4.1 Latest: 1.4.3 [wheel])",
        "awscli (Current: 1.11.63 Latest: 1.12.1 [sdist])",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.list_upgrades()
            mock.assert_called_with(
                [*python_binary, "list", "--outdated"],
                cwd=None,
                runas=None,
            )
            assert ret == {
                "apache-libcloud": "2.2.1 [wheel]",
                "appdirs": "1.4.3 [wheel]",
                "awscli": "1.12.1 [sdist]",
            }


def test_list_upgrades_gt9(python_binary):
    eggs = """[{"latest_filetype": "wheel", "version": "1.1.0", "name": "apache-libcloud", "latest_version": "2.2.1"},
            {"latest_filetype": "wheel", "version": "1.4.1", "name": "appdirs", "latest_version": "1.4.3"},
            {"latest_filetype": "sdist", "version": "1.11.63", "name": "awscli", "latest_version": "1.12.1"}
            ]"""
    mock = MagicMock(return_value={"retcode": 0, "stdout": f"{eggs}"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="9.1.1")):
            ret = pip.list_upgrades()
            mock.assert_called_with(
                [
                    *python_binary,
                    "list",
                    "--outdated",
                    "--format=json",
                ],
                cwd=None,
                runas=None,
            )
            assert ret == {
                "apache-libcloud": "2.2.1 [wheel]",
                "appdirs": "1.4.3 [wheel]",
                "awscli": "1.12.1 [sdist]",
            }


def test_is_installed_true(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pycrypto==2.6",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.is_installed(pkgname="bbfreeze")
            mock.assert_called_with(
                [*python_binary, "freeze"],
                cwd=None,
                runas=None,
                python_shell=False,
                use_vt=False,
            )
            assert ret


def test_is_installed_false(python_binary):
    eggs = [
        "M2Crypto==0.21.1",
        "-e git+git@github.com:s0undt3ch/salt-testing.git@9ed81aa2f918d59d3706e56b18f0782d1ea43bf8#egg=SaltTesting-dev",
        "bbfreeze==1.1.0",
        "bbfreeze-loader==1.1.0",
        "pycrypto==2.6",
    ]
    mock = MagicMock(return_value={"retcode": 0, "stdout": "\n".join(eggs)})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="6.1.1")):
            ret = pip.is_installed(pkgname="notexist")
            mock.assert_called_with(
                [*python_binary, "freeze"],
                cwd=None,
                runas=None,
                python_shell=False,
                use_vt=False,
            )
            assert not ret


def test_install_pre_argument_in_resulting_command(python_binary):
    pkg = "pep8"
    # Lower than 1.4 versions don't end up with `--pre` in the resulting output
    mock = MagicMock(
        side_effect=[
            {"retcode": 0, "stdout": "pip 1.2.0 /path/to/site-packages/pip"},
            {"retcode": 0, "stdout": ""},
        ]
    )
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="1.3")):
            pip.install(pkg, pre_releases=True)
            expected = [*python_binary, "install", *TARGET, pkg]
            mock.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )

    mock_run = MagicMock(return_value="pip 1.4.1 /path/to/site-packages/pip")
    mock_run_all = MagicMock(return_value={"retcode": 0, "stdout": ""})
    with patch.dict(
        pip.__salt__, {"cmd.run_stdout": mock_run, "cmd.run_all": mock_run_all}
    ):
        with patch("salt.modules.pip._get_pip_bin", MagicMock(return_value=["pip"])):
            pip.install(pkg, pre_releases=True)
            expected = ["pip", "install", *TARGET, "--pre", pkg]
            mock_run_all.assert_called_with(
                expected,
                saltenv="base",
                runas=None,
                use_vt=False,
                python_shell=False,
            )


def test_resolve_requirements_chain_function():
    with patch("salt.utils.files.fopen", FakeFopen):
        chain = pip._resolve_requirements_chain(
            ["requirements-0.txt", "requirements-3.txt"]
        )
    assert chain == [
        "requirements-0.txt",
        "requirements-1.txt",
        "requirements-2.txt",
        "requirements-3.txt",
        "requirements-4.txt",
    ]


def test_when_upgrade_is_called_and_there_are_available_upgrades_it_should_call_correct_command(
    expected_user,
):
    fake_run_all = MagicMock(return_value={"retcode": 0, "stdout": "{}"})
    pip_user = expected_user
    with patch.dict(pip.__salt__, {"cmd.run_all": fake_run_all}), patch(
        "salt.modules.pip.list_upgrades", autospec=True, return_value=[pip_user]
    ), patch(
        "salt.modules.pip._get_pip_bin",
        autospec=True,
        return_value=["some-other-pip"],
    ):
        pip.upgrade(user=pip_user)

        fake_run_all.assert_any_call(
            ["some-other-pip", "install", "-U", "list", "--format=json", pip_user],
            runas=pip_user,
            cwd=None,
            use_vt=False,
        )


def test_when_list_upgrades_is_provided_a_user_it_should_be_passed_to_the_version_command(
    expected_user,
):
    fake_run_all = MagicMock(return_value={"retcode": 0, "stdout": "{}"})
    pip_user = expected_user

    def all_new_commands(*args, **kwargs):
        """
        Without this, mutating the return value mutates the return value
        for EVERYTHING.
        """
        return ["some-other-pip"]

    with patch.dict(pip.__salt__, {"cmd.run_all": fake_run_all}), patch(
        "salt.modules.pip._get_pip_bin",
        autospec=True,
        side_effect=all_new_commands,
    ):
        pip._clear_context()
        pip.list_upgrades(user=pip_user)
        fake_run_all.assert_any_call(
            ["some-other-pip", "--version"],
            runas=expected_user,
            cwd=None,
            python_shell=False,
        )


def test_when_install_is_provided_a_user_it_should_be_passed_to_the_version_command(
    expected_user,
):
    fake_run_all = MagicMock(return_value={"retcode": 0, "stdout": "{}"})
    pip_user = expected_user

    def all_new_commands(*args, **kwargs):
        """
        Without this, mutating the return value mutates the return value
        for EVERYTHING.
        """
        return ["some-other-pip"]

    with patch.dict(pip.__salt__, {"cmd.run_all": fake_run_all}), patch(
        "salt.modules.pip._get_pip_bin",
        autospec=True,
        side_effect=all_new_commands,
    ):
        pip._clear_context()
        pip.install(user=pip_user)
        fake_run_all.assert_any_call(
            ["some-other-pip", "--version"],
            runas=pip_user,
            cwd=None,
            python_shell=False,
        )


def test_when_version_is_called_with_a_user_it_should_be_passed_to_undelying_runas(
    expected_user,
):
    fake_run_all = MagicMock(return_value={"retcode": 0, "stdout": ""})
    pip_user = expected_user
    with patch.dict(pip.__salt__, {"cmd.run_all": fake_run_all}), patch(
        "salt.modules.pip.list_upgrades", autospec=True, return_value=[pip_user]
    ), patch(
        "salt.modules.pip._get_pip_bin",
        autospec=True,
        return_value=["some-new-pip"],
    ):
        pip.version(user=pip_user)
        fake_run_all.assert_called_with(
            ["some-new-pip", "--version"],
            runas=pip_user,
            cwd=None,
            python_shell=False,
        )


@pytest.mark.parametrize(
    "bin_env,target,target_env,expected_target",
    [
        (None, None, None, None),
        (None, "/tmp/foo", None, "/tmp/foo"),
        (None, None, "/tmp/bar", "/tmp/bar"),
        (None, "/tmp/foo", "/tmp/bar", "/tmp/foo"),
        ("/tmp/venv", "/tmp/foo", None, "/tmp/foo"),
        ("/tmp/venv", None, "/tmp/bar", None),
        ("/tmp/venv", "/tmp/foo", "/tmp/bar", "/tmp/foo"),
    ],
)
def test_install_target_from_VENV_PIP_TARGET_in_resulting_command(
    python_binary, bin_env, target, target_env, expected_target
):
    pkg = "pep8"
    mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
    environment = os.environ.copy()
    real_get_pip_bin = pip._get_pip_bin

    def mock_get_pip_bin(bin_env):
        if not bin_env:
            return real_get_pip_bin(bin_env)
        return [f"{bin_env}/bin/pip"]

    if target_env is not None:
        environment["VENV_PIP_TARGET"] = target_env
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}), patch.object(
        os, "environ", environment
    ), patch.object(pip, "_get_pip_bin", mock_get_pip_bin):
        pip.install(pkg, bin_env=bin_env, target=target)
        expected_binary = python_binary
        if bin_env is not None:
            expected_binary = [f"{bin_env}/bin/pip"]
        if expected_target is not None:
            expected = [*expected_binary, "install", "--target", expected_target, pkg]
        else:
            expected = [*expected_binary, "install", pkg]
        mock.assert_called_with(
            expected,
            saltenv="base",
            runas=None,
            use_vt=False,
            python_shell=False,
        )


def test_list(python_binary):
    json_out = dedent(
        """
    [
      {
        "name": "idemenv",
        "version": "0.2.0",
        "editable_project_location": "/home/debian/idemenv"
      },
      {
        "name": "MarkupSafe",
        "version": "2.1.1"
      },
      {
        "name": "pip",
        "version": "22.3.1"
      },
      {
        "name": "pop",
        "version": "23.0.0"
      },
      {
        "name": "salt",
        "version": "3006.0+0na.5b18e86"
      },
      {
        "name": "typing_extensions",
        "version": "4.4.0"
      },
      {
        "name": "unattended-upgrades",
        "version": "0.1"
      },
      {
        "name": "yarl",
        "version": "1.8.2"
      }
    ]
    """
    )
    mock_version = "22.3.1"
    mock = MagicMock(return_value={"retcode": 0, "stdout": json_out})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value=mock_version)):
            ret = pip.list_()
            expected = [*python_binary, "list", "--format=json"]
            mock.assert_called_with(
                expected,
                cwd=None,
                runas=None,
                python_shell=False,
            )
            assert ret == {
                "MarkupSafe": "2.1.1",
                "idemenv": "0.2.0",
                "pip": "22.3.1",
                "pop": "23.0.0",
                "salt": "3006.0+0na.5b18e86",
                "typing_extensions": "4.4.0",
                "unattended-upgrades": "0.1",
                "yarl": "1.8.2",
            }

    # Non zero returncode raises exception?
    mock = MagicMock(return_value={"retcode": 1, "stderr": "CABOOOOMMM!"})
    with patch.dict(pip.__salt__, {"cmd.run_all": mock}):
        with patch("salt.modules.pip.version", MagicMock(return_value="22.3.1")):
            pytest.raises(
                CommandExecutionError,
                pip.list_,
            )
