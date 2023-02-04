"""
Tests for building and installing salt
"""
import json
import logging
import pathlib
import re
import sys

import pytest

import salt.utils.path
import salt.utils.platform
import salt.version
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_initial_onedir_failure,
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
]


def _check_skip(grains):
    if grains["os"] == "SUSE":
        return True
    return False


def use_static_requirements_ids(value):
    return "USE_STATIC_REQUIREMENTS={}".format("1" if value else "0")


@pytest.fixture(params=[True, False], ids=use_static_requirements_ids)
def use_static_requirements(request):
    return request.param


@pytest.fixture
def virtualenv(virtualenv, use_static_requirements):
    virtualenv.environ["USE_STATIC_REQUIREMENTS"] = (
        "1" if use_static_requirements else "0"
    )
    return virtualenv


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_wheel(virtualenv, cache_dir, use_static_requirements, src_dir):
    """
    test building and installing a bdist_wheel package
    """
    # Let's create the testing virtualenv
    with virtualenv as venv:
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)
        venv.run(
            venv.venv_python,
            "setup.py",
            "bdist_wheel",
            "--dist-dir",
            str(cache_dir),
            cwd=src_dir,
        )
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        salt_generated_package = list(cache_dir.glob("*.whl"))
        if not salt_generated_package:
            pytest.fail("Could not find the generated wheel file")
        salt_generated_package = salt_generated_package[0]

        # Assert generate wheel version matches what salt reports as its version
        whl_ver = [
            x
            for x in salt_generated_package.name.split("-")
            if re.search(r"^\d.\d*", x)
        ][0]
        whl_ver_cmp = whl_ver.replace("_", "-")
        assert whl_ver_cmp == salt.version.__version__, "{} != {}".format(
            whl_ver_cmp, salt.version.__version__
        )

        # Because bdist_wheel supports pep517, we don't have to pre-install Salt's
        # dependencies before installing the wheel package
        if not use_static_requirements and salt.utils.platform.is_windows():
            # However, on windows, the latest pycurl release, 7.43.0.6 at the time of writing,
            # does not have wheel files uploaded, so, we force pycurl==7.43.0.5 to be
            # pre-installed before installing salt
            venv.install("pycurl==7.43.0.5")
        venv.install(str(salt_generated_package))

        # Let's ensure the version is correct
        cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
        for details in json.loads(cmd.stdout):
            if details["name"] != "salt":
                continue
            installed_version = details["version"]
            break
        else:
            pytest.fail("Salt was not found installed")

        # Let's compare the installed version with the version salt reports
        assert installed_version == salt.version.__version__, "{} != {}".format(
            installed_version, salt.version.__version__
        )

        # Let's also ensure we have a salt/_version.txt from the installed salt wheel
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
        salt_generated_version_file_path = installed_salt_path / "_version.txt"
        assert salt_generated_version_file_path.is_file()


def test_egg(virtualenv, cache_dir, use_static_requirements, src_dir):
    """
    test building and installing a bdist_egg package
    """
    # TODO: We should actually disallow generating an egg file
    # Let's create the testing virtualenv
    with virtualenv as venv:
        ret = venv.run(
            venv.venv_python,
            "-c",
            "import setuptools; print(setuptools.__version__)",
        )
        setuptools_version = ret.stdout.strip()
        ret = venv.run(venv.venv_python, "-m", "easy_install", "--version", check=False)
        if ret.returncode != 0:
            pytest.skip(
                "Setuptools version, {}, does not include the easy_install module".format(
                    setuptools_version
                )
            )
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        # Setuptools installs pre-release packages if we don't pin to an exact version
        # Let's download and install requirements before, running salt's install test
        venv.run(
            venv.venv_python,
            "-m",
            "pip",
            "download",
            "--dest",
            str(cache_dir),
            src_dir,
        )
        packages = []
        for fname in cache_dir.iterdir():
            if (
                fname.name.startswith("pycurl")
                and salt.utils.platform.is_windows()
                and not use_static_requirements
            ):
                # On windows, the latest pycurl release, 7.43.0.6 at the time of writing,
                # does not have wheel files uploaded, so, delete the downloaded source
                # tarball and will later force pycurl==7.43.0.5 to be pre-installed before
                # installing salt
                fname.unlink()
                continue
            packages.append(fname)
        venv.install(*[str(pkg) for pkg in packages])
        for package in packages:
            package.unlink()

        # Looks like, at least on windows, setuptools also get's downloaded as a salt dependency.
        # Let's check and see if this newly installed version also has easy_install
        ret = venv.run(
            venv.venv_python,
            "-c",
            "import setuptools; print(setuptools.__version__)",
        )
        setuptools_version = ret.stdout.strip()
        ret = venv.run(venv.venv_python, "-m", "easy_install", "--version", check=False)
        if ret.returncode != 0:
            pytest.skip(
                "Setuptools version, {}, does not include the easy_install module".format(
                    setuptools_version
                )
            )

        if salt.utils.platform.is_windows() and not use_static_requirements:
            # Like mentioned above, install pycurl==7.43.0.5
            # However, on windows, the latest pycurl release, 7.43.0.6 at the time of writing,
            # does not have wheel files uploaded, so, we force pycurl==7.43.0.5 to be
            # pre-installed before installing salt
            venv.install("pycurl==7.43.0.5")

        venv.run(
            venv.venv_python,
            "setup.py",
            "bdist_egg",
            "--dist-dir",
            str(cache_dir),
            cwd=src_dir,
        )
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        salt_generated_package = list(cache_dir.glob("*.egg"))
        if not salt_generated_package:
            pytest.fail("Could not find the generated egg file")
        salt_generated_package = salt_generated_package[0]

        # Assert generate wheel version matches what salt reports as its version
        egg_ver = [
            x
            for x in salt_generated_package.name.split("-")
            if re.search(r"^\d.\d*", x)
        ][0]
        egg_ver_cmp = egg_ver.replace("_", "-")
        assert egg_ver_cmp == salt.version.__version__, "{} != {}".format(
            egg_ver_cmp, salt.version.__version__
        )

        # We cannot pip install an egg file, let's go old school
        venv.run(venv.venv_python, "-m", "easy_install", str(salt_generated_package))

        # Let's ensure the version is correct
        cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
        for details in json.loads(cmd.stdout):
            if details["name"] != "salt":
                continue
            installed_version = details["version"]
            break
        else:
            pytest.fail("Salt was not found installed")

        # Let's compare the installed version with the version salt reports
        assert installed_version == salt.version.__version__, "{} != {}".format(
            installed_version, salt.version.__version__
        )

        # Let's also ensure we have a salt/_version.txt from the installed salt egg
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
            pytest.fail("Failed to find the installed salt path")
        log.debug("Installed salt path glob matches: %s", installed_salt_path)
        installed_salt_path = installed_salt_path[0] / "salt"
        assert installed_salt_path.is_dir()
        salt_generated_version_file_path = installed_salt_path / "_version.txt"
        assert salt_generated_version_file_path.is_file(), "{} is not a file".format(
            salt_generated_version_file_path
        )


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_sdist(virtualenv, cache_dir, use_static_requirements, src_dir):
    """
    test building and installing a sdist package
    """
    # Let's create the testing virtualenv
    with virtualenv as venv:
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        # Setuptools installs pre-release packages if we don't pin to an exact version
        # Let's download and install requirements before, running salt's install test
        venv.run(
            venv.venv_python,
            "-m",
            "pip",
            "download",
            "--dest",
            str(cache_dir),
            src_dir,
        )
        packages = []
        for fname in cache_dir.iterdir():
            if (
                fname.name.startswith("pycurl")
                and salt.utils.platform.is_windows()
                and not use_static_requirements
            ):
                # On windows, the latest pycurl release, 7.43.0.6 at the time of writing,
                # does not have wheel files uploaded, so, delete the downloaded source
                # tarball and will later force pycurl==7.43.0.5 to be pre-installed before
                # installing salt
                fname.unlink()
                continue
            packages.append(fname)
        venv.install(*[str(pkg) for pkg in packages])
        for package in packages:
            package.unlink()

        if salt.utils.platform.is_windows() and not use_static_requirements:
            # Like mentioned above, install pycurl==7.43.0.5
            # However, on windows, the latest pycurl release, 7.43.0.6 at the time of writing,
            # does not have wheel files uploaded, so, we force pycurl==7.43.0.5 to be
            # pre-installed before installing salt
            venv.install("pycurl==7.43.0.5")

        venv.run(
            venv.venv_python,
            "setup.py",
            "sdist",
            "--dist-dir",
            str(cache_dir),
            cwd=src_dir,
        )

        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        salt_generated_package = list(cache_dir.glob("*.tar.gz"))
        if not salt_generated_package:
            pytest.fail("Could not find the generated sdist file")
        salt_generated_package = salt_generated_package[0]
        log.info("Generated sdist file: %s", salt_generated_package.name)

        # Assert generated sdist version matches what salt reports as its version
        sdist_ver_cmp = salt_generated_package.name.split(".tar.gz")[0].split("salt-")[
            -1
        ]
        assert sdist_ver_cmp == salt.version.__version__, "{} != {}".format(
            sdist_ver_cmp, salt.version.__version__
        )

        venv.install(str(salt_generated_package))

        # Let's also ensure we have a salt/_version.txt from the installed salt wheel
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
        salt_generated_version_file_path = installed_salt_path / "_version.txt"
        assert salt_generated_version_file_path.is_file()
        with salt_generated_version_file_path.open() as rfh:
            log.debug("_version.txt contents:\n >>>>>>\n%s\n <<<<<<", rfh.read())

        # Let's ensure the version is correct
        cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
        for details in json.loads(cmd.stdout):
            if details["name"] != "salt":
                continue
            installed_version = details["version"]
            break
        else:
            pytest.fail("Salt was not found installed")

        # Let's compare the installed version with the version salt reports
        assert installed_version == salt.version.__version__, "{} != {}".format(
            installed_version, salt.version.__version__
        )


@pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip)
def test_setup_install(virtualenv, cache_dir, use_static_requirements, src_dir):
    """
    test installing directly from source
    """
    # Let's create the testing virtualenv
    with virtualenv as venv:
        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        # Setuptools installs pre-release packages if we don't pin to an exact version
        # Let's download and install requirements before, running salt's install test
        venv.run(
            venv.venv_python,
            "-m",
            "pip",
            "download",
            "--dest",
            str(cache_dir),
            src_dir,
        )
        packages = []
        for fname in cache_dir.iterdir():
            if (
                fname.name.startswith("pycurl")
                and salt.utils.platform.is_windows()
                and not use_static_requirements
            ):
                # On windows, the latest pycurl release, 7.43.0.6 at the time of writing,
                # does not have wheel files uploaded, so, delete the downloaded source
                # tarball and will later force pycurl==7.43.0.5 to be pre-installed before
                # installing salt
                fname.unlink()
                continue
            packages.append(fname)
        venv.install(*[str(pkg) for pkg in packages])
        for package in packages:
            package.unlink()

        if salt.utils.platform.is_windows() and not use_static_requirements:
            # Like mentioned above, install pycurl==7.43.0.5
            # However, on windows, the latest pycurl release, 7.43.0.6 at the time of writing,
            # does not have wheel files uploaded, so, we force pycurl==7.43.0.5 to be
            # pre-installed before installing salt
            venv.install("pycurl==7.43.0.5")

        venv.run(
            venv.venv_python,
            "setup.py",
            "install",
            "--prefix",
            str(venv.venv_dir),
            cwd=src_dir,
        )

        venv.run(venv.venv_python, "setup.py", "clean", cwd=src_dir)

        # Let's ensure the version is correct
        cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
        for details in json.loads(cmd.stdout):
            if details["name"] != "salt":
                continue
            installed_version = details["version"]
            break
        else:
            pytest.fail("Salt was not found installed")

        # Let's compare the installed version with the version salt reports
        assert installed_version == salt.version.__version__, "{} != {}".format(
            installed_version, salt.version.__version__
        )

        # Let's also ensure we have a salt/_version.txt from the installed salt
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
            pytest.fail("Failed to find the installed salt path")
        installed_salt_path = installed_salt_path[0] / "salt"
        salt_generated_version_file_path = installed_salt_path / "_version.txt"
        assert salt_generated_version_file_path.is_file()
