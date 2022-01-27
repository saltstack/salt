"""
tests.unit.states.pip_test
~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging
import os
import subprocess
import sys

import pytest
import salt.states.pip_state as pip_state
import salt.utils.path
import salt.version
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, dedent
from tests.support.mixins import LoaderModuleMockMixin, SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

try:
    import pip

    HAS_PIP = True
except ImportError:
    HAS_PIP = False


log = logging.getLogger(__name__)


@skipIf(not HAS_PIP, "The 'pip' library is not importable(installed system-wide)")
class PipStateTest(TestCase, SaltReturnAssertsMixin, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            pip_state: {
                "__env__": "base",
                "__opts__": {"test": False},
                "__salt__": {"cmd.which_bin": lambda _: "pip"},
            }
        }

    def test_install_requirements_parsing(self):
        log.debug("Real pip version is %s", pip.__version__)
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        pip_list = MagicMock(return_value={"pep8": "1.3.3"})
        pip_version = pip.__version__
        mock_pip_version = MagicMock(return_value=pip_version)
        with patch.dict(pip_state.__salt__, {"pip.version": mock_pip_version}):
            with patch.dict(
                pip_state.__salt__, {"cmd.run_all": mock, "pip.list": pip_list}
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    log.debug(
                        "pip_state._from_line globals: %s",
                        [name for name in pip_state._from_line.__globals__],
                    )
                    ret = pip_state.installed("pep8=1.3.2")
                    self.assertSaltFalseReturn({"test": ret})
                    self.assertInSaltComment(
                        "Invalid version specification in package pep8=1.3.2. "
                        "'=' is not supported, use '==' instead.",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.3"})
            pip_install = MagicMock(return_value={"retcode": 0})
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed("pep8>=1.3.2")
                    self.assertSaltTrueReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package pep8>=1.3.2 was already installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.3"})
            with patch.dict(
                pip_state.__salt__, {"cmd.run_all": mock, "pip.list": pip_list}
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed("pep8<1.3.2")
                    self.assertSaltNoneReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package pep8<1.3.2 is set to be installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.2"})
            pip_install = MagicMock(return_value={"retcode": 0})
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed("pep8>1.3.1,<1.3.3")
                    self.assertSaltTrueReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package pep8>1.3.1,<1.3.3 was already installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.1"})
            pip_install = MagicMock(return_value={"retcode": 0})
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed("pep8>1.3.1,<1.3.3")
                    self.assertSaltNoneReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package pep8>1.3.1,<1.3.3 is set to be installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.1"})
            with patch.dict(
                pip_state.__salt__, {"cmd.run_all": mock, "pip.list": pip_list}
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed(
                        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting>=0.5.1"
                    )
                    self.assertSaltNoneReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package git+https://github.com/saltstack/"
                        "salt-testing.git#egg=SaltTesting>=0.5.1 is set to be "
                        "installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.1"})
            with patch.dict(
                pip_state.__salt__, {"cmd.run_all": mock, "pip.list": pip_list}
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed(
                        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting"
                    )
                    self.assertSaltNoneReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package git+https://github.com/saltstack/"
                        "salt-testing.git#egg=SaltTesting is set to be "
                        "installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.1"})
            with patch.dict(
                pip_state.__salt__, {"cmd.run_all": mock, "pip.list": pip_list}
            ):
                with patch.dict(pip_state.__opts__, {"test": True}):
                    ret = pip_state.installed(
                        "https://pypi.python.org/packages/source/S/SaltTesting/"
                        "SaltTesting-0.5.0.tar.gz"
                        "#md5=e6760af92b7165f8be53b5763e40bc24"
                    )
                    self.assertSaltNoneReturn({"test": ret})
                    self.assertInSaltComment(
                        "Python package https://pypi.python.org/packages/source/"
                        "S/SaltTesting/SaltTesting-0.5.0.tar.gz"
                        "#md5=e6760af92b7165f8be53b5763e40bc24 is set to be "
                        "installed",
                        {"test": ret},
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"SaltTesting": "0.5.0"})
            pip_install = MagicMock(
                return_value={
                    "retcode": 0,
                    "stderr": "",
                    "stdout": (
                        "Downloading/unpacking https://pypi.python.org/packages"
                        "/source/S/SaltTesting/SaltTesting-0.5.0.tar.gz\n  "
                        "Downloading SaltTesting-0.5.0.tar.gz\n  Running "
                        "setup.py egg_info for package from "
                        "https://pypi.python.org/packages/source/S/SaltTesting/"
                        "SaltTesting-0.5.0.tar.gz\n    \nCleaning up..."
                    ),
                }
            )
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                ret = pip_state.installed(
                    "https://pypi.python.org/packages/source/S/SaltTesting/"
                    "SaltTesting-0.5.0.tar.gz"
                    "#md5=e6760af92b7165f8be53b5763e40bc24"
                )
                self.assertSaltTrueReturn({"test": ret})
                self.assertInSaltComment(
                    "All packages were successfully installed", {"test": ret}
                )
                self.assertInSaltReturn(
                    "Installed",
                    {"test": ret},
                    (
                        "changes",
                        "https://pypi.python.org/packages/source/S/"
                        "SaltTesting/SaltTesting-0.5.0.tar.gz"
                        "#md5=e6760af92b7165f8be53b5763e40bc24==???",
                    ),
                )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"SaltTesting": "0.5.0"})
            pip_install = MagicMock(
                return_value={"retcode": 0, "stderr": "", "stdout": "Cloned!"}
            )
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": False}):
                    ret = pip_state.installed(
                        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting"
                    )
                    self.assertSaltTrueReturn({"test": ret})
                    self.assertInSaltComment(
                        "packages are already installed", {"test": ret}
                    )

            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"pep8": "1.3.1"})
            pip_install = MagicMock(return_value={"retcode": 0})
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": False}):
                    ret = pip_state.installed(
                        "arbitrary ID that should be ignored due to requirements"
                        " specified",
                        requirements="/tmp/non-existing-requirements.txt",
                    )
                    self.assertSaltTrueReturn({"test": ret})

            # Test VCS installations using git+git://
            mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
            pip_list = MagicMock(return_value={"SaltTesting": "0.5.0"})
            pip_install = MagicMock(
                return_value={"retcode": 0, "stderr": "", "stdout": "Cloned!"}
            )
            with patch.dict(
                pip_state.__salt__,
                {"cmd.run_all": mock, "pip.list": pip_list, "pip.install": pip_install},
            ):
                with patch.dict(pip_state.__opts__, {"test": False}):
                    ret = pip_state.installed(
                        "git+git://github.com/saltstack/salt-testing.git#egg=SaltTesting"
                    )
                    self.assertSaltTrueReturn({"test": ret})
                    self.assertInSaltComment(
                        "packages are already installed", {"test": ret}
                    )

    def test_install_requirements_custom_pypi(self):
        """
        test requirement parsing for both when a custom
        pypi index-url is set and when it is not and
        the requirement is already installed.
        """

        # create requirements file
        req_filename = os.path.join(
            RUNTIME_VARS.TMP_STATE_TREE, "custom-pypi-requirements.txt"
        )
        with salt.utils.files.fopen(req_filename, "wb") as reqf:
            reqf.write(b"pep8\n")

        site_pkgs = "/tmp/pip-env/lib/python3.7/site-packages"
        check_stdout = [
            "Looking in indexes: https://custom-pypi-url.org,"
            "https://pypi.org/simple/\nRequirement already satisfied: pep8 in {1}"
            "(from -r /tmp/files/prod/{0} (line 1)) (1.7.1)".format(
                req_filename, site_pkgs
            ),
            "Requirement already satisfied: pep8 in {1}"
            "(from -r /tmp/files/prod/{0} (line1)) (1.7.1)".format(
                req_filename, site_pkgs
            ),
        ]
        pip_version = pip.__version__
        mock_pip_version = MagicMock(return_value=pip_version)

        for stdout in check_stdout:
            pip_install = MagicMock(return_value={"retcode": 0, "stdout": stdout})
            with patch.dict(pip_state.__salt__, {"pip.version": mock_pip_version}):
                with patch.dict(pip_state.__salt__, {"pip.install": pip_install}):
                    ret = pip_state.installed(name="", requirements=req_filename)
                    self.assertSaltTrueReturn({"test": ret})
                    assert "Requirements were already installed." == ret["comment"]

    def test_install_requirements_custom_pypi_changes(self):
        """
        test requirement parsing for both when a custom
        pypi index-url is set and when it is not and
        the requirement is not installed.
        """

        # create requirements file
        req_filename = os.path.join(
            RUNTIME_VARS.TMP_STATE_TREE, "custom-pypi-requirements.txt"
        )
        with salt.utils.files.fopen(req_filename, "wb") as reqf:
            reqf.write(b"pep8\n")

        site_pkgs = "/tmp/pip-env/lib/python3.7/site-packages"
        check_stdout = [
            "Looking in indexes:"
            " https://custom-pypi-url.org,https://pypi.org/simple/\nCollecting pep8\n "
            " Using"
            " cachedhttps://custom-pypi-url.org//packages/42/3f/669429cef5acb4/pep8-1.7.1-py2.py3-none-any.whl"
            " (41 kB)\nInstalling collected packages: pep8\nSuccessfully installed"
            " pep8-1.7.1",
            "Collecting pep8\n  Using"
            " cachedhttps://custom-pypi-url.org//packages/42/3f/669429cef5acb4/pep8-1.7.1-py2.py3-none-any.whl"
            " (41 kB)\nInstalling collected packages: pep8\nSuccessfully installed"
            " pep8-1.7.1",
        ]

        pip_version = pip.__version__
        mock_pip_version = MagicMock(return_value=pip_version)

        for stdout in check_stdout:
            pip_install = MagicMock(return_value={"retcode": 0, "stdout": stdout})
            with patch.dict(pip_state.__salt__, {"pip.version": mock_pip_version}):
                with patch.dict(pip_state.__salt__, {"pip.install": pip_install}):
                    ret = pip_state.installed(name="", requirements=req_filename)
                    self.assertSaltTrueReturn({"test": ret})
                    assert (
                        "Successfully processed requirements file {}.".format(
                            req_filename
                        )
                        == ret["comment"]
                    )

    def test_install_in_editable_mode(self):
        """
        Check that `name` parameter containing bad characters is not parsed by
        pip when package is being installed in editable mode.
        For more information, see issue #21890.
        """
        mock = MagicMock(return_value={"retcode": 0, "stdout": ""})
        pip_list = MagicMock(return_value={})
        pip_install = MagicMock(
            return_value={"retcode": 0, "stderr": "", "stdout": "Cloned!"}
        )
        pip_version = MagicMock(return_value="10.0.1")
        with patch.dict(
            pip_state.__salt__,
            {
                "cmd.run_all": mock,
                "pip.list": pip_list,
                "pip.install": pip_install,
                "pip.version": pip_version,
            },
        ):
            ret = pip_state.installed(
                "state@name", cwd="/path/to/project", editable=["."]
            )
            self.assertSaltTrueReturn({"test": ret})
            self.assertInSaltComment("successfully installed", {"test": ret})


class PipStateUtilsTest(TestCase):
    def test_has_internal_exceptions_mod_function(self):
        assert pip_state.pip_has_internal_exceptions_mod("10.0")
        assert pip_state.pip_has_internal_exceptions_mod("18.1")
        assert not pip_state.pip_has_internal_exceptions_mod("9.99")

    def test_has_exceptions_mod_function(self):
        assert pip_state.pip_has_exceptions_mod("1.0")
        assert not pip_state.pip_has_exceptions_mod("0.1")
        assert not pip_state.pip_has_exceptions_mod("10.0")

    def test_pip_purge_method_with_pip(self):
        mock_modules = sys.modules.copy()
        mock_modules.pop("pip", None)
        mock_modules["pip"] = object()
        with patch("sys.modules", mock_modules):
            pip_state.purge_pip()
        assert "pip" not in mock_modules

    def test_pip_purge_method_without_pip(self):
        mock_modules = sys.modules.copy()
        mock_modules.pop("pip", None)
        with patch("sys.modules", mock_modules):
            pip_state.purge_pip()


@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
@pytest.mark.requires_network
class PipStateInstallationErrorTest(TestCase):
    @pytest.mark.slow_test
    def test_importable_installation_error(self):
        extra_requirements = []
        for name, version in salt.version.dependency_information():
            if name in ["PyYAML"]:
                extra_requirements.append("{}=={}".format(name, version))
        failures = {}
        pip_version_requirements = [
            # Latest pip 8
            "<9.0",
            # Latest pip 9
            "<10.0",
            # Latest pip 18
            "<19.0",
            # Latest pip 19
            "<20.0",
            # Latest pip 20
            "<21.0",
            # Latest pip
            None,
        ]
        code = dedent(
            """\
        import sys
        import traceback
        try:
            import salt.states.pip_state
            salt.states.pip_state.InstallationError
        except ImportError as exc:
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            sys.exit(1)
        except AttributeError as exc:
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            sys.exit(2)
        except Exception as exc:
            traceback.print_exc(exc, file=sys.stdout)
            sys.stdout.flush()
            sys.exit(3)
        sys.exit(0)
        """
        )
        for requirement in list(pip_version_requirements):
            try:
                with VirtualEnv() as venv:
                    venv.install(*extra_requirements)
                    if requirement:
                        venv.install("pip{}".format(requirement))
                    try:
                        subprocess.check_output([venv.venv_python, "-c", code])
                    except subprocess.CalledProcessError as exc:
                        if exc.returncode == 1:
                            failures[requirement] = "Failed to import pip:\n{}".format(
                                exc.output
                            )
                        elif exc.returncode == 2:
                            failures[
                                requirement
                            ] = "Failed to import InstallationError from pip:\n{}".format(
                                exc.output
                            )
                        else:
                            failures[requirement] = exc.output
            except Exception as exc:  # pylint: disable=broad-except
                failures[requirement] = str(exc)
        if failures:
            errors = ""
            for requirement, exception in failures.items():
                errors += "pip{}: {}\n\n".format(requirement or "", exception)
            self.fail(
                "Failed to get InstallationError exception under at least one pip"
                " version:\n{}".format(errors)
            )
