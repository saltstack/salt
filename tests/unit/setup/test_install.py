"""
tests.unit.setup.test_install
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import json
import logging
import os
import pathlib
import re
import sys

import salt.utils.path
import salt.utils.platform
import salt.version
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, slowTest, with_tempdir
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class InstallTest(TestCase):
    """
    Tests for building and installing salt
    """

    @slowTest
    @with_tempdir()
    def test_wheel(self, tempdir):
        """
        test building and installing a bdist_wheel package
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)
            venv.run(
                venv.venv_python,
                "setup.py",
                "bdist_wheel",
                "--dist-dir",
                tempdir,
                cwd=RUNTIME_VARS.CODE_DIR,
            )
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            salt_generated_package = list(pathlib.Path(tempdir).glob("*.whl"))
            if not salt_generated_package:
                self.fail("Could not find the generated wheel file")
            salt_generated_package = salt_generated_package[0]

            # Assert generate wheel version matches what salt reports as its version
            whl_ver = [
                x
                for x in salt_generated_package.name.split("-")
                if re.search(r"^\d.\d*", x)
            ][0]
            whl_ver_cmp = whl_ver.replace("_", "-")
            salt_ver_cmp = salt.version.__version__.replace("/", "-")
            assert whl_ver_cmp == salt_ver_cmp, "{} != {}".format(
                whl_ver_cmp, salt_ver_cmp
            )

            # Because bdist_wheel supports pep517, we don't have to pre-install Salt's
            # dependencies before installing the wheel package
            venv.install(str(salt_generated_package))

            # Let's ensure the version is correct
            cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
            for details in json.loads(cmd.stdout):
                if details["name"] != "salt":
                    continue
                installed_version = details["version"]
                break
            else:
                self.fail("Salt was not found installed")

            # Let's compare the installed version with the version salt reports
            assert installed_version == salt_ver_cmp, "{} != {}".format(
                installed_version, salt_ver_cmp
            )

            # Let's also ensure we have a salt/_version.py from the installed salt wheel
            subdir = [
                "lib",
                "python{}.{}".format(*sys.version_info),
                "site-packages",
                "salt",
            ]
            if salt.utils.platform.is_windows():
                subdir.pop(1)

            installed_salt_path = pathlib.Path(venv.venv_dir)
            installed_salt_path = installed_salt_path.joinpath(*subdir)
            assert installed_salt_path.is_dir()
            salt_generated_version_file_path = installed_salt_path / "_version.py"
            assert salt_generated_version_file_path.is_file()

    @slowTest
    @with_tempdir()
    def test_egg(self, tempdir):
        """
        test building and installing a bdist_egg package
        """
        # TODO: We should actually dissallow generating an egg file
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            # Setuptools installs pre-release packages if we don't pin to an exact version
            # Let's download and install requirements before, running salt's install test
            venv.run(
                venv.venv_python,
                "-m",
                "pip",
                "download",
                "--dest",
                tempdir,
                RUNTIME_VARS.CODE_DIR,
            )
            packages = []
            for fname in os.listdir(tempdir):
                packages.append(os.path.join(tempdir, fname))
            venv.install(*packages)
            for package in packages:
                os.unlink(package)

            venv.run(
                venv.venv_python,
                "setup.py",
                "bdist_egg",
                "--dist-dir",
                tempdir,
                cwd=RUNTIME_VARS.CODE_DIR,
            )
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            salt_generated_package = list(pathlib.Path(tempdir).glob("*.egg"))
            if not salt_generated_package:
                self.fail("Could not find the generated egg file")
            salt_generated_package = salt_generated_package[0]

            # Assert generate wheel version matches what salt reports as its version
            egg_ver = [
                x
                for x in salt_generated_package.name.split("-")
                if re.search(r"^\d.\d*", x)
            ][0]
            egg_ver_cmp = egg_ver.replace("_", "-")
            salt_ver_cmp = salt.version.__version__.replace("/", "-")
            assert egg_ver_cmp == salt_ver_cmp, "{} != {}".format(
                egg_ver_cmp, salt_ver_cmp
            )

            # We cannot pip install an egg file, let's go old school
            venv.run(
                venv.venv_python, "-m", "easy_install", str(salt_generated_package)
            )

            # Let's ensure the version is correct
            cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
            for details in json.loads(cmd.stdout):
                if details["name"] != "salt":
                    continue
                installed_version = details["version"]
                break
            else:
                self.fail("Salt was not found installed")

            # Let's compare the installed version with the version salt reports
            assert installed_version == salt_ver_cmp, "{} != {}".format(
                installed_version, salt_ver_cmp
            )

            # Let's also ensure we have a salt/_version.py from the installed salt egg
            subdir = [
                "lib",
                "python{}.{}".format(*sys.version_info),
                "site-packages",
            ]
            if salt.utils.platform.is_windows():
                subdir.pop(1)
            site_packages_dir = pathlib.Path(venv.venv_dir)
            site_packages_dir = site_packages_dir.joinpath(*subdir)
            assert site_packages_dir.is_dir()
            installed_salt_path = list(site_packages_dir.glob("salt*.egg"))
            if not installed_salt_path:
                self.fail("Failed to find the installed salt path")
            log.debug("Installed salt path glob matches: %s", installed_salt_path)
            installed_salt_path = installed_salt_path[0] / "salt"
            assert installed_salt_path.is_dir()
            salt_generated_version_file_path = installed_salt_path / "_version.py"
            assert (
                salt_generated_version_file_path.is_file()
            ), "{} is not a file".format(salt_generated_version_file_path)

    # On python 3.5 Windows sdist fails with encoding errors. This is resolved
    # in later versions.
    @skipIf(
        salt.utils.platform.is_windows()
        and sys.version_info > (3,)
        and sys.version_info < (3, 6),
        "Skip on python 3.5",
    )
    @slowTest
    @with_tempdir()
    def test_sdist(self, tempdir):
        """
        test building and installing a sdist package
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            # Setuptools installs pre-release packages if we don't pin to an exact version
            # Let's download and install requirements before, running salt's install test
            venv.run(
                venv.venv_python,
                "-m",
                "pip",
                "download",
                "--dest",
                tempdir,
                RUNTIME_VARS.CODE_DIR,
            )
            packages = []
            for fname in os.listdir(tempdir):
                packages.append(os.path.join(tempdir, fname))
            venv.install(*packages)
            for package in packages:
                os.unlink(package)

            venv.run(
                venv.venv_python,
                "setup.py",
                "sdist",
                "--dist-dir",
                tempdir,
                cwd=RUNTIME_VARS.CODE_DIR,
            )
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            salt_generated_package = list(pathlib.Path(tempdir).glob("*.tar.gz"))
            if not salt_generated_package:
                self.fail("Could not find the generated sdist file")
            salt_generated_package = salt_generated_package[0]
            log.info("Generated sdist file: %s", salt_generated_package.name)

            # Assert generated sdist version matches what salt reports as its version
            sdist_ver_cmp = salt_generated_package.name.split(".tar.gz")[0].split(
                "salt-"
            )[-1]
            salt_ver_cmp = salt.version.__version__.replace("/", "-")
            assert sdist_ver_cmp == salt_ver_cmp, "{} != {}".format(
                sdist_ver_cmp, salt.version.__version__
            )

            venv.install(str(salt_generated_package))

            # Let's also ensure we have a salt/_version.py from the installed salt wheel
            subdir = [
                "lib",
                "python{}.{}".format(*sys.version_info),
                "site-packages",
                "salt",
            ]
            if salt.utils.platform.is_windows():
                subdir.pop(1)

            installed_salt_path = pathlib.Path(venv.venv_dir)
            installed_salt_path = installed_salt_path.joinpath(*subdir)
            assert installed_salt_path.is_dir()
            salt_generated_version_file_path = installed_salt_path / "_version.py"
            assert salt_generated_version_file_path.is_file()
            with salt_generated_version_file_path.open() as rfh:
                log.debug("_version.py contents:\n >>>>>>\n%s\n <<<<<<", rfh.read())

            # Let's ensure the version is correct
            cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
            for details in json.loads(cmd.stdout):
                if details["name"] != "salt":
                    continue
                installed_version = details["version"]
                break
            else:
                self.fail("Salt was not found installed")

            # Let's compare the installed version with the version salt reports
            assert installed_version == salt_ver_cmp, "{} != {}".format(
                installed_version, salt_ver_cmp
            )

    @slowTest
    @with_tempdir()
    def test_setup_install(self, tempdir):
        """
        test installing directly from source
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            # Setuptools installs pre-release packages if we don't pin to an exact version
            # Let's download and install requirements before, running salt's install test
            venv.run(
                venv.venv_python,
                "-m",
                "pip",
                "download",
                "--dest",
                tempdir,
                RUNTIME_VARS.CODE_DIR,
            )
            packages = []
            for fname in os.listdir(tempdir):
                packages.append(os.path.join(tempdir, fname))
            venv.install(*packages)
            for package in packages:
                os.unlink(package)

            venv.run(
                venv.venv_python,
                "setup.py",
                "install",
                "--prefix",
                venv.venv_dir,
                cwd=RUNTIME_VARS.CODE_DIR,
            )

            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            # Let's ensure the version is correct
            cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
            for details in json.loads(cmd.stdout):
                if details["name"] != "salt":
                    continue
                installed_version = details["version"]
                break
            else:
                self.fail("Salt was not found installed")

            salt_ver_cmp = salt.version.__version__.replace("/", "-")
            # Let's compare the installed version with the version salt reports
            assert installed_version == salt_ver_cmp, "{} != {}".format(
                installed_version, salt_ver_cmp
            )

            # Let's also ensure we have a salt/_version.py from the installed salt
            subdir = [
                "lib",
                "python{}.{}".format(*sys.version_info),
                "site-packages",
            ]
            if salt.utils.platform.is_windows():
                subdir.pop(1)
            site_packages_dir = pathlib.Path(venv.venv_dir)
            site_packages_dir = site_packages_dir.joinpath(*subdir)
            assert site_packages_dir.is_dir()
            installed_salt_path = list(site_packages_dir.glob("salt*.egg"))
            if not installed_salt_path:
                self.fail("Failed to find the installed salt path")
            installed_salt_path = installed_salt_path[0] / "salt"
            salt_generated_version_file_path = installed_salt_path / "_version.py"
            assert salt_generated_version_file_path.is_file()
