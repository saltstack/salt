#!/usr/bin/env python
"""
The setup script for salt
"""

# pylint: disable=file-perms,resource-leakage
import contextlib
import distutils.dist
import glob
import operator
import os
import platform
import sys
from ctypes.util import find_library
from datetime import datetime

# pylint: disable=no-name-in-module
from distutils import log
from distutils.cmd import Command
from distutils.command.build import build
from distutils.command.clean import clean
from distutils.command.install_lib import install_lib
from distutils.errors import DistutilsArgError
from distutils.version import LooseVersion  # pylint: disable=blacklisted-module

import setuptools
from setuptools import setup
from setuptools.command.bdist_egg import bdist_egg
from setuptools.command.develop import develop
from setuptools.command.install import install
from setuptools.command.sdist import sdist

# pylint: enable=no-name-in-module


try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen  # pylint: disable=no-name-in-module


try:
    from wheel.bdist_wheel import bdist_wheel

    HAS_BDIST_WHEEL = True
except ImportError:
    HAS_BDIST_WHEEL = False

try:
    import zmq

    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False

try:
    DATE = datetime.utcfromtimestamp(int(os.environ["SOURCE_DATE_EPOCH"]))
except (KeyError, ValueError):
    DATE = datetime.utcnow()

# Change to salt source's directory prior to running any command
try:
    SETUP_DIRNAME = os.path.dirname(__file__)
except NameError:
    # We're most likely being frozen and __file__ triggered this NameError
    # Let's work around that
    SETUP_DIRNAME = os.path.dirname(sys.argv[0])

if SETUP_DIRNAME != "":
    os.chdir(SETUP_DIRNAME)

SETUP_DIRNAME = os.path.abspath(SETUP_DIRNAME)

BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION = os.environ.get(
    # The user can provide a different bootstrap-script version.
    # ATTENTION: A tag for that version MUST exist
    "BOOTSTRAP_SCRIPT_VERSION",
    # If no bootstrap-script version was provided from the environment, let's
    # provide the one we define.
    "v2014.06.21",
)

# Store a reference to the executing platform
IS_OSX_PLATFORM = sys.platform.startswith("darwin")
IS_WINDOWS_PLATFORM = sys.platform.startswith("win")
if IS_WINDOWS_PLATFORM or IS_OSX_PLATFORM:
    IS_SMARTOS_PLATFORM = False
else:
    # os.uname() not available on Windows.
    IS_SMARTOS_PLATFORM = os.uname()[0] == "SunOS" and os.uname()[3].startswith(
        "joyent_"
    )

USE_STATIC_REQUIREMENTS = os.environ.get("USE_STATIC_REQUIREMENTS")
if USE_STATIC_REQUIREMENTS is not None:
    USE_STATIC_REQUIREMENTS = USE_STATIC_REQUIREMENTS == "1"

try:
    # Add the esky bdist target if the module is available
    # may require additional modules depending on platform
    # bbfreeze chosen for its tight integration with distutils
    import bbfreeze  # pylint: disable=unused-import
    from esky import bdist_esky  # pylint: disable=unused-import

    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

SALT_VERSION = os.path.join(os.path.abspath(SETUP_DIRNAME), "salt", "version.py")
SALT_VERSION_HARDCODED = os.path.join(
    os.path.abspath(SETUP_DIRNAME), "salt", "_version.py"
)
SALT_SYSPATHS_HARDCODED = os.path.join(
    os.path.abspath(SETUP_DIRNAME), "salt", "_syspaths.py"
)
SALT_BASE_REQUIREMENTS = [
    os.path.join(os.path.abspath(SETUP_DIRNAME), "requirements", "base.txt"),
    # pyzmq needs to be installed regardless of the salt transport
    os.path.join(os.path.abspath(SETUP_DIRNAME), "requirements", "zeromq.txt"),
    os.path.join(os.path.abspath(SETUP_DIRNAME), "requirements", "crypto.txt"),
]
SALT_LINUX_LOCKED_REQS = [
    # Linux packages defined locked requirements
    os.path.join(
        os.path.abspath(SETUP_DIRNAME),
        "requirements",
        "static",
        "pkg",
        "py{}.{}".format(*sys.version_info),
        "linux.txt",
    )
]
SALT_OSX_REQS = SALT_BASE_REQUIREMENTS + [
    os.path.join(os.path.abspath(SETUP_DIRNAME), "requirements", "darwin.txt")
]
SALT_OSX_LOCKED_REQS = [
    # OSX packages already defined locked requirements
    os.path.join(
        os.path.abspath(SETUP_DIRNAME),
        "requirements",
        "static",
        "pkg",
        "py{}.{}".format(*sys.version_info),
        "darwin.txt",
    )
]
SALT_WINDOWS_REQS = SALT_BASE_REQUIREMENTS + [
    os.path.join(os.path.abspath(SETUP_DIRNAME), "requirements", "windows.txt")
]
SALT_WINDOWS_LOCKED_REQS = [
    # Windows packages already defined locked requirements
    os.path.join(
        os.path.abspath(SETUP_DIRNAME),
        "requirements",
        "static",
        "pkg",
        "py{}.{}".format(*sys.version_info),
        "windows.txt",
    )
]
SALT_LONG_DESCRIPTION_FILE = os.path.join(os.path.abspath(SETUP_DIRNAME), "README.rst")

# Salt SSH Packaging Detection
PACKAGED_FOR_SALT_SSH_FILE = os.path.join(
    os.path.abspath(SETUP_DIRNAME), ".salt-ssh-package"
)
PACKAGED_FOR_SALT_SSH = os.path.isfile(PACKAGED_FOR_SALT_SSH_FILE)


# pylint: disable=W0122
exec(compile(open(SALT_VERSION).read(), SALT_VERSION, "exec"))
# pylint: enable=W0122


# ----- Helper Functions -------------------------------------------------------------------------------------------->


def _parse_op(op):
    """
    >>> _parse_op('>')
    'gt'
    >>> _parse_op('>=')
    'ge'
    >>> _parse_op('=>')
    'ge'
    >>> _parse_op('=> ')
    'ge'
    >>> _parse_op('<')
    'lt'
    >>> _parse_op('<=')
    'le'
    >>> _parse_op('==')
    'eq'
    >>> _parse_op(' <= ')
    'le'
    """
    op = op.strip()
    if ">" in op:
        if "=" in op:
            return "ge"
        else:
            return "gt"
    elif "<" in op:
        if "=" in op:
            return "le"
        else:
            return "lt"
    elif "!" in op:
        return "ne"
    else:
        return "eq"


def _parse_ver(ver):
    """
    >>> _parse_ver("'3.4'  # pyzmq 17.1.0 stopped building wheels for python3.4")
    '3.4'
    >>> _parse_ver('"3.4"')
    '3.4'
    >>> _parse_ver('"2.6.17"')
    '2.6.17'
    """
    if "#" in ver:
        ver, _ = ver.split("#", 1)
        ver = ver.strip()
    return ver.strip("'").strip('"')


def _check_ver(pyver, op, wanted):
    """
    >>> _check_ver('2.7.15', 'gt', '2.7')
    True
    >>> _check_ver('2.7.15', 'gt', '2.7.15')
    False
    >>> _check_ver('2.7.15', 'ge', '2.7.15')
    True
    >>> _check_ver('2.7.15', 'eq', '2.7.15')
    True
    """
    pyver = distutils.version.LooseVersion(pyver)
    wanted = distutils.version.LooseVersion(wanted)
    if not isinstance(pyver, str):
        pyver = str(pyver)
    if not isinstance(wanted, str):
        wanted = str(wanted)
    return getattr(operator, "__{}__".format(op))(pyver, wanted)


def _parse_requirements_file(requirements_file):
    parsed_requirements = []
    with open(requirements_file) as rfh:
        for line in rfh.readlines():
            line = line.strip()
            if not line or line.startswith(("#", "-r", "--")):
                continue
            if IS_WINDOWS_PLATFORM:
                if "libcloud" in line:
                    continue
            try:
                pkg, pyverspec = line.rsplit(";", 1)
            except ValueError:
                pkg, pyverspec = line, ""
            pyverspec = pyverspec.strip()
            if pyverspec and (
                not pkg.startswith("pycrypto") or pkg.startswith("pycryptodome")
            ):
                _, op, ver = pyverspec.split(" ", 2)
                if not _check_ver(
                    platform.python_version(), _parse_op(op), _parse_ver(ver)
                ):
                    continue
            parsed_requirements.append(pkg)
    return parsed_requirements


# <---- Helper Functions ---------------------------------------------------------------------------------------------


# ----- Custom Distutils/Setuptools Commands ------------------------------------------------------------------------>
class WriteSaltVersion(Command):

    description = "Write salt's hardcoded version file"
    user_options = []

    def initialize_options(self):
        """
        Abstract method that is required to be overwritten
        """

    def finalize_options(self):
        """
        Abstract method that is required to be overwritten
        """

    def run(self):
        if (
            not os.path.exists(SALT_VERSION_HARDCODED)
            or self.distribution.with_salt_version
        ):
            # Write the version file
            if getattr(self.distribution, "salt_version_hardcoded_path", None) is None:
                self.distribution.salt_version_hardcoded_path = SALT_VERSION_HARDCODED
                sys.stderr.write("This command is not meant to be called on it's own\n")
                sys.stderr.flush()

            if not self.distribution.with_salt_version:
                salt_version = (
                    __saltstack_version__  # pylint: disable=undefined-variable
                )
            else:
                from salt.version import SaltStackVersion

                salt_version = SaltStackVersion.parse(
                    self.distribution.with_salt_version
                )

            # pylint: disable=E0602
            open(self.distribution.salt_version_hardcoded_path, "w").write(
                INSTALL_VERSION_TEMPLATE.format(
                    date=DATE, full_version_info=salt_version.full_info_all_versions
                )
            )
            # pylint: enable=E0602


class GenerateSaltSyspaths(Command):

    description = "Generate salt's hardcoded syspaths file"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # Write the syspaths file
        if getattr(self.distribution, "salt_syspaths_hardcoded_path", None) is None:
            print("This command is not meant to be called on it's own")
            exit(1)

        # Write the system paths file
        open(self.distribution.salt_syspaths_hardcoded_path, "w").write(
            INSTALL_SYSPATHS_TEMPLATE.format(
                date=DATE,
                root_dir=self.distribution.salt_root_dir,
                share_dir=self.distribution.salt_share_dir,
                config_dir=self.distribution.salt_config_dir,
                cache_dir=self.distribution.salt_cache_dir,
                sock_dir=self.distribution.salt_sock_dir,
                srv_root_dir=self.distribution.salt_srv_root_dir,
                base_file_roots_dir=self.distribution.salt_base_file_roots_dir,
                base_pillar_roots_dir=self.distribution.salt_base_pillar_roots_dir,
                base_master_roots_dir=self.distribution.salt_base_master_roots_dir,
                base_thorium_roots_dir=self.distribution.salt_base_thorium_roots_dir,
                logs_dir=self.distribution.salt_logs_dir,
                pidfile_dir=self.distribution.salt_pidfile_dir,
                spm_parent_path=self.distribution.salt_spm_parent_dir,
                spm_formula_path=self.distribution.salt_spm_formula_dir,
                spm_pillar_path=self.distribution.salt_spm_pillar_dir,
                spm_reactor_path=self.distribution.salt_spm_reactor_dir,
                home_dir=self.distribution.salt_home_dir,
            )
        )


class WriteSaltSshPackagingFile(Command):

    description = "Write salt's ssh packaging file"
    user_options = []

    def initialize_options(self):
        """
        Abstract method that is required to be overwritten
        """

    def finalize_options(self):
        """
        Abstract method that is required to be overwritten
        """

    def run(self):
        if not os.path.exists(PACKAGED_FOR_SALT_SSH_FILE):
            # Write the salt-ssh packaging file
            if getattr(self.distribution, "salt_ssh_packaging_file", None) is None:
                print("This command is not meant to be called on it's own")
                exit(1)

            # pylint: disable=E0602
            open(self.distribution.salt_ssh_packaging_file, "w").write(
                "Packaged for Salt-SSH\n"
            )
            # pylint: enable=E0602


class Develop(develop):
    user_options = develop.user_options + [
        (
            "write-salt-version",
            None,
            "Generate Salt's _version.py file which allows proper version "
            "reporting. This defaults to False on develop/editable setups. "
            "If WRITE_SALT_VERSION is found in the environment this flag is "
            "switched to True.",
        ),
        (
            "generate-salt-syspaths",
            None,
            "Generate Salt's _syspaths.py file which allows tweaking some "
            "common paths that salt uses. This defaults to False on "
            "develop/editable setups. If GENERATE_SALT_SYSPATHS is found in "
            "the environment this flag is switched to True.",
        ),
        (
            "mimic-salt-install",
            None,
            "Mimmic the install command when running the develop command. "
            "This will generate salt's _version.py and _syspaths.py files. "
            "Generate Salt's _syspaths.py file which allows tweaking some "
            "This defaults to False on develop/editable setups. "
            "If MIMIC_INSTALL is found in the environment this flag is "
            "switched to True.",
        ),
    ]
    boolean_options = develop.boolean_options + [
        "write-salt-version",
        "generate-salt-syspaths",
        "mimic-salt-install",
    ]

    def initialize_options(self):
        develop.initialize_options(self)
        self.write_salt_version = False
        self.generate_salt_syspaths = False
        self.mimic_salt_install = False

    def finalize_options(self):
        develop.finalize_options(self)
        if "WRITE_SALT_VERSION" in os.environ:
            self.write_salt_version = True
        if "GENERATE_SALT_SYSPATHS" in os.environ:
            self.generate_salt_syspaths = True
        if "MIMIC_SALT_INSTALL" in os.environ:
            self.mimic_salt_install = True

        if self.mimic_salt_install:
            self.write_salt_version = True
            self.generate_salt_syspaths = True

    def run(self):
        if IS_WINDOWS_PLATFORM:
            # Download the required DLLs
            self.distribution.salt_download_windows_dlls = True
            self.run_command("download-windows-dlls")
            self.distribution.salt_download_windows_dlls = None

        if self.write_salt_version is True:
            self.distribution.running_salt_install = True
            self.distribution.salt_version_hardcoded_path = SALT_VERSION_HARDCODED
            self.run_command("write_salt_version")

        if self.generate_salt_syspaths:
            self.distribution.salt_syspaths_hardcoded_path = SALT_SYSPATHS_HARDCODED
            self.run_command("generate_salt_syspaths")

        # Resume normal execution
        develop.run(self)


class DownloadWindowsDlls(Command):

    description = "Download required DLL's for windows"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if getattr(self.distribution, "salt_download_windows_dlls", None) is None:
            print("This command is not meant to be called on it's own")
            exit(1)
        try:
            import pip

            # pip has moved many things to `_internal` starting with pip 10
            if LooseVersion(pip.__version__) < LooseVersion("10.0"):
                # pylint: disable=no-name-in-module
                from pip.utils.logging import indent_log

                # pylint: enable=no-name-in-module
            else:
                from pip._internal.utils.logging import (  # pylint: disable=no-name-in-module
                    indent_log,
                )
        except ImportError:
            # TODO: Impliment indent_log here so we don't require pip
            @contextlib.contextmanager
            def indent_log():
                yield

        platform_bits, _ = platform.architecture()
        url = "https://repo.saltproject.io/windows/dependencies/{bits}/{fname}"
        dest = os.path.join(os.path.dirname(sys.executable), "{fname}")
        with indent_log():
            for fname in (
                "openssl/1.1.1k/ssleay32.dll",
                "openssl/1.1.1k/libeay32.dll",
                "libsodium/1.0.18/libsodium.dll",
            ):
                # See if the library is already on the system
                if find_library(fname):
                    continue
                furl = url.format(bits=platform_bits[:2], fname=fname)
                fdest = dest.format(fname=os.path.basename(fname))
                if not os.path.exists(fdest):
                    log.info("Downloading {} to {} from {}".format(fname, fdest, furl))
                    try:
                        from contextlib import closing

                        import requests

                        with closing(requests.get(furl, stream=True)) as req:
                            if req.status_code == 200:
                                with open(fdest, "wb") as wfh:
                                    for chunk in req.iter_content(chunk_size=4096):
                                        if chunk:  # filter out keep-alive new chunks
                                            wfh.write(chunk)
                                            wfh.flush()
                            else:
                                log.error(
                                    "Failed to download {} to {} from {}".format(
                                        fname, fdest, furl
                                    )
                                )
                    except ImportError:
                        req = urlopen(furl)

                        if req.getcode() == 200:
                            with open(fdest, "wb") as wfh:
                                while True:
                                    chunk = req.read(4096)
                                    if not chunk:
                                        break
                                    wfh.write(chunk)
                                    wfh.flush()
                        else:
                            log.error(
                                "Failed to download {} to {} from {}".format(
                                    fname, fdest, furl
                                )
                            )


class Sdist(sdist):
    def make_release_tree(self, base_dir, files):
        if self.distribution.ssh_packaging:
            self.distribution.salt_ssh_packaging_file = PACKAGED_FOR_SALT_SSH_FILE
            self.run_command("write_salt_ssh_packaging_file")
            self.filelist.files.append(os.path.basename(PACKAGED_FOR_SALT_SSH_FILE))

        sdist.make_release_tree(self, base_dir, files)

        # Let's generate salt/_version.py to include in the sdist tarball
        self.distribution.running_salt_sdist = True
        self.distribution.salt_version_hardcoded_path = os.path.join(
            base_dir, "salt", "_version.py"
        )
        self.run_command("write_salt_version")

    def make_distribution(self):
        sdist.make_distribution(self)
        if self.distribution.ssh_packaging:
            os.unlink(PACKAGED_FOR_SALT_SSH_FILE)


class BDistEgg(bdist_egg):
    def finalize_options(self):
        bdist_egg.finalize_options(self)
        self.distribution.build_egg = True
        if not self.skip_build:
            self.run_command("build")


class CloudSdist(Sdist):  # pylint: disable=too-many-ancestors
    user_options = Sdist.user_options + [
        (
            "download-bootstrap-script",
            None,
            "Download the latest stable bootstrap-salt.sh script. This "
            "can also be triggered by having `DOWNLOAD_BOOTSTRAP_SCRIPT=1` as an "
            "environment variable.",
        )
    ]
    boolean_options = Sdist.boolean_options + ["download-bootstrap-script"]

    def initialize_options(self):
        Sdist.initialize_options(self)
        self.skip_bootstrap_download = True
        self.download_bootstrap_script = False

    def finalize_options(self):
        Sdist.finalize_options(self)
        if "SKIP_BOOTSTRAP_DOWNLOAD" in os.environ:
            # pylint: disable=not-callable
            log(
                "Please stop using 'SKIP_BOOTSTRAP_DOWNLOAD' and use "
                "'DOWNLOAD_BOOTSTRAP_SCRIPT' instead"
            )
            # pylint: enable=not-callable

        if "DOWNLOAD_BOOTSTRAP_SCRIPT" in os.environ:
            download_bootstrap_script = os.environ.get("DOWNLOAD_BOOTSTRAP_SCRIPT", "0")
            self.download_bootstrap_script = download_bootstrap_script == "1"

    def run(self):
        if self.download_bootstrap_script is True:
            # Let's update the bootstrap-script to the version defined to be
            # distributed. See BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION above.
            url = (
                "https://github.com/saltstack/salt-bootstrap/raw/{}"
                "/bootstrap-salt.sh".format(BOOTSTRAP_SCRIPT_DISTRIBUTED_VERSION)
            )
            deploy_path = os.path.join(
                SETUP_DIRNAME, "salt", "cloud", "deploy", "bootstrap-salt.sh"
            )
            log.info(
                "Updating bootstrap-salt.sh."
                "\n\tSource:      {}"
                "\n\tDestination: {}".format(url, deploy_path)
            )

            try:
                import requests

                req = requests.get(url)
                if req.status_code == 200:
                    script_contents = req.text.encode(req.encoding)
                else:
                    log.error(
                        "Failed to update the bootstrap-salt.sh script. HTTP "
                        "Error code: {}".format(req.status_code)
                    )
            except ImportError:
                req = urlopen(url)

                if req.getcode() == 200:
                    script_contents = req.read()
                else:
                    log.error(
                        "Failed to update the bootstrap-salt.sh script. HTTP "
                        "Error code: {}".format(req.getcode())
                    )
            try:
                with open(deploy_path, "w") as fp_:
                    fp_.write(script_contents)
            except OSError as err:
                log.error("Failed to write the updated script: {}".format(err))

        # Let's the rest of the build command
        Sdist.run(self)

    def write_manifest(self):
        # We only need to ship the scripts which are supposed to be installed
        dist_scripts = self.distribution.scripts
        for script in self.filelist.files[:]:
            if not script.startswith("scripts/"):
                continue
            if script not in dist_scripts:
                self.filelist.files.remove(script)
        return Sdist.write_manifest(self)


class TestCommand(Command):
    description = "Run tests"
    user_options = [
        ("runtests-opts=", "R", "Command line options to pass to runtests.py")
    ]

    def initialize_options(self):
        self.runtests_opts = None

    def finalize_options(self):
        """
        Abstract method that is required to be overwritten
        """

    def run(self):
        # This should either be removed or migrated to use nox
        import subprocess

        self.run_command("build")
        build_cmd = self.get_finalized_command("build_ext")
        runner = os.path.abspath("tests/runtests.py")
        test_cmd = [sys.executable, runner]
        if self.runtests_opts:
            test_cmd.extend(self.runtests_opts.split())

        print("running test")
        ret = subprocess.run(
            test_cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=build_cmd.build_lib,
            check=False,
        )
        sys.exit(ret.returncode)


class Clean(clean):
    def run(self):
        clean.run(self)
        # Let's clean compiled *.py[c,o]
        for subdir in ("salt", "tests", "doc"):
            root = os.path.join(os.path.dirname(__file__), subdir)
            for dirname, _, _ in os.walk(root):
                for to_remove_filename in glob.glob("{}/*.py[oc]".format(dirname)):
                    os.remove(to_remove_filename)


if HAS_BDIST_WHEEL:

    class BDistWheel(bdist_wheel):
        def finalize_options(self):
            bdist_wheel.finalize_options(self)
            self.distribution.build_wheel = True


INSTALL_VERSION_TEMPLATE = """\
# This file was auto-generated by salt's setup

from salt.version import SaltStackVersion

__saltstack_version__ = SaltStackVersion{full_version_info!r}
"""


INSTALL_SYSPATHS_TEMPLATE = """\
# This file was auto-generated by salt's setup on \
{date:%A, %d %B %Y @ %H:%m:%S UTC}.

ROOT_DIR = {root_dir!r}
SHARE_DIR = {share_dir!r}
CONFIG_DIR = {config_dir!r}
CACHE_DIR = {cache_dir!r}
SOCK_DIR = {sock_dir!r}
SRV_ROOT_DIR= {srv_root_dir!r}
BASE_FILE_ROOTS_DIR = {base_file_roots_dir!r}
BASE_PILLAR_ROOTS_DIR = {base_pillar_roots_dir!r}
BASE_MASTER_ROOTS_DIR = {base_master_roots_dir!r}
BASE_THORIUM_ROOTS_DIR = {base_thorium_roots_dir!r}
LOGS_DIR = {logs_dir!r}
PIDFILE_DIR = {pidfile_dir!r}
SPM_PARENT_PATH = {spm_parent_path!r}
SPM_FORMULA_PATH = {spm_formula_path!r}
SPM_PILLAR_PATH = {spm_pillar_path!r}
SPM_REACTOR_PATH = {spm_reactor_path!r}
HOME_DIR = {home_dir!r}
"""


class Build(build):
    def run(self):
        # Run build.run function
        build.run(self)
        salt_build_ver_file = os.path.join(self.build_lib, "salt", "_version.py")

        if getattr(self.distribution, "with_salt_version", False):
            # Write the hardcoded salt version module salt/_version.py
            self.distribution.salt_version_hardcoded_path = salt_build_ver_file
            self.run_command("write_salt_version")

        if getattr(self.distribution, "build_egg", False):
            # we are building an egg package. need to include _version.py
            self.distribution.salt_version_hardcoded_path = salt_build_ver_file
            self.run_command("write_salt_version")

        if getattr(self.distribution, "build_wheel", False):
            # we are building a wheel package. need to include _version.py
            self.distribution.salt_version_hardcoded_path = salt_build_ver_file
            self.run_command("write_salt_version")

        if getattr(self.distribution, "running_salt_install", False):
            # If our install attribute is present and set to True, we'll go
            # ahead and write our install time python modules.

            # Write the hardcoded salt version module salt/_version.py
            self.run_command("write_salt_version")

            # Write the system paths file
            self.distribution.salt_syspaths_hardcoded_path = os.path.join(
                self.build_lib, "salt", "_syspaths.py"
            )
            self.run_command("generate_salt_syspaths")


class Install(install):
    def initialize_options(self):
        install.initialize_options(self)

    def finalize_options(self):
        install.finalize_options(self)

    def run(self):
        if LooseVersion(setuptools.__version__) < LooseVersion("9.1"):
            sys.stderr.write(
                "\n\nInstalling Salt requires setuptools >= 9.1\n"
                "Available setuptools version is {}\n\n".format(setuptools.__version__)
            )
            sys.stderr.flush()
            sys.exit(1)

        # Let's set the running_salt_install attribute so we can add
        # _version.py in the build command
        self.distribution.running_salt_install = True
        self.distribution.salt_version_hardcoded_path = os.path.join(
            self.build_lib, "salt", "_version.py"
        )
        if IS_WINDOWS_PLATFORM:
            # Download the required DLLs
            self.distribution.salt_download_windows_dlls = True
            self.run_command("download-windows-dlls")
            self.distribution.salt_download_windows_dlls = None
        # need to ensure _version.py is created in build dir before install
        if not os.path.exists(os.path.join(self.build_lib)):
            if not self.skip_build:
                self.run_command("build")
        else:
            self.run_command("write_salt_version")
        # Run install.run
        install.run(self)

    @staticmethod
    def _called_from_setup(run_frame):
        """
        Attempt to detect whether run() was called from setup() or by another
        command.  If called by setup(), the parent caller will be the
        'run_command' method in 'distutils.dist', and *its* caller will be
        the 'run_commands' method.  If called any other way, the
        immediate caller *might* be 'run_command', but it won't have been
        called by 'run_commands'. Return True in that case or if a call stack
        is unavailable. Return False otherwise.
        """
        if run_frame is None:
            # If run_frame is None, just call the parent class logic
            return install._called_from_setup(run_frame)

        # Because Salt subclasses the setuptools install command, it needs to
        # override this static method to provide the right frame for the logic
        # so apply.

        # We first try the current run_frame in case the issue
        # https://github.com/pypa/setuptools/issues/456 is fixed.
        first_call = install._called_from_setup(run_frame)
        if first_call:
            return True

        # Fallback to providing the parent frame to have the right logic kick in
        second_call = install._called_from_setup(run_frame.f_back)
        if second_call is None:
            # There was no parent frame?!
            return first_call
        return second_call


class InstallLib(install_lib):
    def run(self):
        executables = [
            "salt/templates/git/ssh-id-wrapper",
            "salt/templates/lxc/salt_tarball",
        ]
        install_lib.run(self)

        # input and outputs match 1-1
        inp = self.get_inputs()
        out = self.get_outputs()
        chmod = []

        for idx, inputfile in enumerate(inp):
            for executable in executables:
                if inputfile.endswith(executable):
                    chmod.append(idx)
        for idx in chmod:
            filename = out[idx]
            os.chmod(filename, 0o755)


# <---- Custom Distutils/Setuptools Commands -------------------------------------------------------------------------


# ----- Custom Distribution Class ----------------------------------------------------------------------------------->
# We use this to override the package name in case --ssh-packaging is passed to
# setup.py or the special .salt-ssh-package is found
class SaltDistribution(distutils.dist.Distribution):
    """
    Just so it's completely clear

    Under windows, the following scripts should be installed:

        * salt-call
        * salt-cp
        * salt-minion
        * salt-syndic
        * salt-unity
        * spm

    When packaged for salt-ssh, the following scripts should be installed:
        * salt-call
        * salt-run
        * salt-ssh
        * salt-cloud

        Under windows, the following scripts should be omitted from the salt-ssh
        package:
            * salt-cloud
            * salt-run

    Under *nix, all scripts should be installed
    """

    global_options = (
        distutils.dist.Distribution.global_options
        + [
            ("ssh-packaging", None, "Run in SSH packaging mode"),
            (
                "salt-transport=",
                None,
                "The transport to prepare salt for. Currently, the only choice "
                "is 'zeromq'. This may be expanded in the future. Defaults to "
                "'zeromq'",
                "zeromq",
            ),
        ]
        + [
            (
                "with-salt-version=",
                None,
                "Set a fixed version for Salt instead calculating it",
            ),
            # Salt's Paths Configuration Settings
            ("salt-root-dir=", None, "Salt's pre-configured root directory"),
            ("salt-share-dir=", None, "Salt's pre-configured share directory"),
            ("salt-config-dir=", None, "Salt's pre-configured configuration directory"),
            ("salt-cache-dir=", None, "Salt's pre-configured cache directory"),
            ("salt-sock-dir=", None, "Salt's pre-configured socket directory"),
            ("salt-srv-root-dir=", None, "Salt's pre-configured service directory"),
            (
                "salt-base-file-roots-dir=",
                None,
                "Salt's pre-configured file roots directory",
            ),
            (
                "salt-base-pillar-roots-dir=",
                None,
                "Salt's pre-configured pillar roots directory",
            ),
            (
                "salt-base-master-roots-dir=",
                None,
                "Salt's pre-configured master roots directory",
            ),
            ("salt-logs-dir=", None, "Salt's pre-configured logs directory"),
            ("salt-pidfile-dir=", None, "Salt's pre-configured pidfiles directory"),
            (
                "salt-spm-formula-dir=",
                None,
                "Salt's pre-configured SPM formulas directory",
            ),
            (
                "salt-spm-pillar-dir=",
                None,
                "Salt's pre-configured SPM pillar directory",
            ),
            (
                "salt-spm-reactor-dir=",
                None,
                "Salt's pre-configured SPM reactor directory",
            ),
            ("salt-home-dir=", None, "Salt's pre-configured user home directory"),
        ]
    )

    def __init__(self, attrs=None):
        distutils.dist.Distribution.__init__(self, attrs)

        self.ssh_packaging = PACKAGED_FOR_SALT_SSH
        self.salt_transport = None

        # Salt Paths Configuration Settings
        self.salt_root_dir = None
        self.salt_share_dir = None
        self.salt_config_dir = None
        self.salt_cache_dir = None
        self.salt_sock_dir = None
        self.salt_srv_root_dir = None
        self.salt_base_file_roots_dir = None
        self.salt_base_thorium_roots_dir = None
        self.salt_base_pillar_roots_dir = None
        self.salt_base_master_roots_dir = None
        self.salt_logs_dir = None
        self.salt_pidfile_dir = None
        self.salt_spm_parent_dir = None
        self.salt_spm_formula_dir = None
        self.salt_spm_pillar_dir = None
        self.salt_spm_reactor_dir = None
        self.salt_home_dir = None

        # Salt version
        self.with_salt_version = None

        self.name = "salt-ssh" if PACKAGED_FOR_SALT_SSH else "salt"
        self.salt_version = __version__  # pylint: disable=undefined-variable
        self.description = (
            "Portable, distributed, remote execution and configuration management"
            " system"
        )
        with open(SALT_LONG_DESCRIPTION_FILE, encoding="utf-8") as f:
            self.long_description = f.read()
        self.long_description_content_type = "text/x-rst"
        self.python_requires = ">=3.5"
        self.classifiers = [
            "Programming Language :: Python",
            "Programming Language :: Cython",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3 :: Only",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Development Status :: 5 - Production/Stable",
            "Environment :: Console",
            "Intended Audience :: Developers",
            "Intended Audience :: Information Technology",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: POSIX :: Linux",
            "Topic :: System :: Clustering",
            "Topic :: System :: Distributed Computing",
        ]
        self.author = "Thomas S Hatch"
        self.author_email = "thatch45@gmail.com"
        self.url = "https://saltproject.io"
        self.cmdclass.update(
            {
                "test": TestCommand,
                "clean": Clean,
                "build": Build,
                "sdist": Sdist,
                "bdist_egg": BDistEgg,
                "install": Install,
                "develop": Develop,
                "write_salt_version": WriteSaltVersion,
                "generate_salt_syspaths": GenerateSaltSyspaths,
                "write_salt_ssh_packaging_file": WriteSaltSshPackagingFile,
            }
        )
        if not IS_WINDOWS_PLATFORM:
            self.cmdclass.update({"sdist": CloudSdist, "install_lib": InstallLib})
        if IS_WINDOWS_PLATFORM:
            self.cmdclass.update({"download-windows-dlls": DownloadWindowsDlls})
        if HAS_BDIST_WHEEL:
            self.cmdclass["bdist_wheel"] = BDistWheel

        self.license = "Apache Software License 2.0"
        self.packages = self.discover_packages()
        self.zip_safe = False

        if HAS_ESKY:
            self.setup_esky()

        self.update_metadata()

    def update_metadata(self):
        for attrname in dir(self):
            if attrname.startswith("__"):
                continue
            attrvalue = getattr(self, attrname, None)
            if attrvalue == 0:
                continue
            if attrname == "salt_version":
                attrname = "version"
            if hasattr(self.metadata, "set_{}".format(attrname)):
                getattr(self.metadata, "set_{}".format(attrname))(attrvalue)
            elif hasattr(self.metadata, attrname):
                try:
                    setattr(self.metadata, attrname, attrvalue)
                except AttributeError:
                    pass

    def discover_packages(self):
        modules = []
        for root, _, files in os.walk(os.path.join(SETUP_DIRNAME, "salt")):
            if "__init__.py" not in files:
                continue
            modules.append(os.path.relpath(root, SETUP_DIRNAME).replace(os.sep, "."))
        return modules

    # ----- Static Data -------------------------------------------------------------------------------------------->
    @property
    def _property_dependency_links(self):
        return [
            "https://github.com/saltstack/salt-testing/tarball/develop#egg=SaltTesting"
        ]

    @property
    def _property_tests_require(self):
        return ["SaltTesting"]

    # <---- Static Data ----------------------------------------------------------------------------------------------

    # ----- Dynamic Data -------------------------------------------------------------------------------------------->
    @property
    def _property_package_data(self):
        package_data = {
            "salt.templates": [
                "rh_ip/*.jinja",
                "debian_ip/*.jinja",
                "virt/*.jinja",
                "git/*",
                "lxc/*",
            ]
        }
        if not IS_WINDOWS_PLATFORM:
            package_data["salt.cloud"] = ["deploy/*.sh"]

        if not self.ssh_packaging and not PACKAGED_FOR_SALT_SSH:
            package_data["salt.daemons.flo"] = ["*.flo"]
        return package_data

    @property
    def _property_data_files(self):
        # Data files common to all scenarios
        data_files = [
            ("share/man/man1", ["doc/man/salt-call.1", "doc/man/salt-run.1"]),
            ("share/man/man7", ["doc/man/salt.7"]),
        ]
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            data_files[0][1].append("doc/man/salt-ssh.1")
            if IS_WINDOWS_PLATFORM:
                return data_files
            data_files[0][1].append("doc/man/salt-cloud.1")

            return data_files

        if IS_WINDOWS_PLATFORM:
            data_files[0][1].extend(
                [
                    "doc/man/salt-api.1",
                    "doc/man/salt-cp.1",
                    "doc/man/salt-key.1",
                    "doc/man/salt-minion.1",
                    "doc/man/salt-syndic.1",
                    "doc/man/salt-unity.1",
                    "doc/man/spm.1",
                ]
            )
            return data_files

        # *nix, so, we need all man pages
        data_files[0][1].extend(
            [
                "doc/man/salt-api.1",
                "doc/man/salt-cloud.1",
                "doc/man/salt-cp.1",
                "doc/man/salt-key.1",
                "doc/man/salt-master.1",
                "doc/man/salt-minion.1",
                "doc/man/salt-proxy.1",
                "doc/man/spm.1",
                "doc/man/salt.1",
                "doc/man/salt-ssh.1",
                "doc/man/salt-syndic.1",
                "doc/man/salt-unity.1",
            ]
        )
        return data_files

    @property
    def _property_install_requires(self):
        install_requires = []
        if USE_STATIC_REQUIREMENTS is True:
            # We've been explicitly asked to use static requirements
            if IS_OSX_PLATFORM:
                for reqfile in SALT_OSX_LOCKED_REQS:
                    install_requires += _parse_requirements_file(reqfile)

            elif IS_WINDOWS_PLATFORM:
                for reqfile in SALT_WINDOWS_LOCKED_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            else:
                for reqfile in SALT_LINUX_LOCKED_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            return install_requires
        elif USE_STATIC_REQUIREMENTS is False:
            # We've been explicitly asked NOT to use static requirements
            if IS_OSX_PLATFORM:
                for reqfile in SALT_OSX_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            elif IS_WINDOWS_PLATFORM:
                for reqfile in SALT_WINDOWS_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            else:
                for reqfile in SALT_BASE_REQUIREMENTS:
                    install_requires += _parse_requirements_file(reqfile)
        else:
            # This is the old and default behavior
            if IS_OSX_PLATFORM:
                for reqfile in SALT_OSX_LOCKED_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            elif IS_WINDOWS_PLATFORM:
                for reqfile in SALT_WINDOWS_LOCKED_REQS:
                    install_requires += _parse_requirements_file(reqfile)
            else:
                for reqfile in SALT_BASE_REQUIREMENTS:
                    install_requires += _parse_requirements_file(reqfile)
        return install_requires

    @property
    def _property_scripts(self):
        # Scripts common to all scenarios
        scripts = ["scripts/salt-call", "scripts/salt-run"]
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            scripts.append("scripts/salt-ssh")
            if IS_WINDOWS_PLATFORM:
                return scripts
            scripts.extend(["scripts/salt-cloud", "scripts/spm"])
            return scripts

        if IS_WINDOWS_PLATFORM:
            scripts.extend(
                [
                    "scripts/salt-api",
                    "scripts/salt-cp",
                    "scripts/salt-key",
                    "scripts/salt-minion",
                    "scripts/salt-syndic",
                    "scripts/salt-unity",
                    "scripts/spm",
                ]
            )
            return scripts

        # *nix, so, we need all scripts
        scripts.extend(
            [
                "scripts/salt",
                "scripts/salt-api",
                "scripts/salt-cloud",
                "scripts/salt-cp",
                "scripts/salt-key",
                "scripts/salt-master",
                "scripts/salt-minion",
                "scripts/salt-proxy",
                "scripts/salt-ssh",
                "scripts/salt-syndic",
                "scripts/salt-unity",
                "scripts/spm",
            ]
        )
        return scripts

    @property
    def _property_entry_points(self):
        # console scripts common to all scenarios
        scripts = [
            "salt-call = salt.scripts:salt_call",
            "salt-run = salt.scripts:salt_run",
        ]
        if self.ssh_packaging or PACKAGED_FOR_SALT_SSH:
            scripts.append("salt-ssh = salt.scripts:salt_ssh")
            if IS_WINDOWS_PLATFORM:
                return {"console_scripts": scripts}
            scripts.append("salt-cloud = salt.scripts:salt_cloud")
            return {"console_scripts": scripts}

        if IS_WINDOWS_PLATFORM:
            scripts.extend(
                [
                    "salt-api = salt.scripts:salt_api",
                    "salt-cp = salt.scripts:salt_cp",
                    "salt-key = salt.scripts:salt_key",
                    "salt-minion = salt.scripts:salt_minion",
                    "salt-syndic = salt.scripts:salt_syndic",
                    "salt-unity = salt.scripts:salt_unity",
                    "spm = salt.scripts:salt_spm",
                ]
            )
            return {"console_scripts": scripts}

        # *nix, so, we need all scripts
        scripts.extend(
            [
                "salt = salt.scripts:salt_main",
                "salt-api = salt.scripts:salt_api",
                "salt-cloud = salt.scripts:salt_cloud",
                "salt-cp = salt.scripts:salt_cp",
                "salt-key = salt.scripts:salt_key",
                "salt-master = salt.scripts:salt_master",
                "salt-minion = salt.scripts:salt_minion",
                "salt-ssh = salt.scripts:salt_ssh",
                "salt-syndic = salt.scripts:salt_syndic",
                "salt-unity = salt.scripts:salt_unity",
                "spm = salt.scripts:salt_spm",
            ]
        )
        return {"console_scripts": scripts}

    # <---- Dynamic Data ---------------------------------------------------------------------------------------------

    # ----- Esky Setup ---------------------------------------------------------------------------------------------->
    def setup_esky(self):
        opt_dict = self.get_option_dict("bdist_esky")
        opt_dict["freezer_module"] = ("setup script", "bbfreeze")
        opt_dict["freezer_options"] = (
            "setup script",
            {"includes": self.get_esky_freezer_includes()},
        )

    @property
    def _property_freezer_options(self):
        return {"includes": self.get_esky_freezer_includes()}

    def get_esky_freezer_includes(self):
        # Sometimes the auto module traversal doesn't find everything, so we
        # explicitly add it. The auto dependency tracking especially does not work for
        # imports occurring in salt.modules, as they are loaded at salt runtime.
        # Specifying includes that don't exist doesn't appear to cause a freezing
        # error.
        freezer_includes = [
            "zmq.core.*",
            "zmq.utils.*",
            "ast",
            "csv",
            "difflib",
            "distutils",
            "distutils.version",
            "numbers",
            "json",
            "M2Crypto",
            "Cookie",
            "asyncore",
            "fileinput",
            "sqlite3",
            "email",
            "email.mime.*",
            "requests",
            "sqlite3",
        ]
        if HAS_ZMQ and hasattr(zmq, "pyzmq_version_info"):
            if HAS_ZMQ and zmq.pyzmq_version_info() >= (0, 14):
                # We're freezing, and when freezing ZMQ needs to be installed, so this
                # works fine
                if "zmq.core.*" in freezer_includes:
                    # For PyZMQ >= 0.14, freezing does not need 'zmq.core.*'
                    freezer_includes.remove("zmq.core.*")

        if IS_WINDOWS_PLATFORM:
            freezer_includes.extend(
                [
                    "imp",
                    "win32api",
                    "win32file",
                    "win32con",
                    "win32com",
                    "win32net",
                    "win32netcon",
                    "win32gui",
                    "win32security",
                    "ntsecuritycon",
                    "pywintypes",
                    "pythoncom",
                    "_winreg",
                    "wmi",
                    "site",
                    "psutil",
                    "pytz",
                ]
            )
        elif IS_SMARTOS_PLATFORM:
            # we have them as requirements in pkg/smartos/esky/requirements.txt
            # all these should be safe to force include
            freezer_includes.extend(
                ["cherrypy", "python-dateutil", "pyghmi", "croniter", "mako", "gnupg"]
            )
        elif sys.platform.startswith("linux"):
            freezer_includes.append("spwd")
            try:
                import yum  # pylint: disable=unused-import

                freezer_includes.append("yum")
            except ImportError:
                pass
        elif sys.platform.startswith("sunos"):
            # (The sledgehammer approach)
            # Just try to include everything
            # (This may be a better way to generate freezer_includes generally)
            try:
                from bbfreeze.modulegraph.modulegraph import ModuleGraph

                mgraph = ModuleGraph(sys.path[:])
                for arg in glob.glob("salt/modules/*.py"):
                    mgraph.run_script(arg)
                for mod in mgraph.flatten():
                    if type(mod).__name__ != "Script" and mod.filename:
                        freezer_includes.append(str(os.path.basename(mod.identifier)))
            except ImportError:
                pass

        return freezer_includes

    # <---- Esky Setup -----------------------------------------------------------------------------------------------

    # ----- Overridden Methods -------------------------------------------------------------------------------------->
    def parse_command_line(self):
        args = distutils.dist.Distribution.parse_command_line(self)

        if not self.ssh_packaging and PACKAGED_FOR_SALT_SSH:
            self.ssh_packaging = 1

        if self.ssh_packaging:
            self.metadata.name = "salt-ssh"
            self.salt_transport = "ssh"
        elif self.salt_transport is None:
            self.salt_transport = "zeromq"

        if self.salt_transport not in ("zeromq", "both", "ssh", "none"):
            raise DistutilsArgError(
                "The value of --salt-transport needs be 'zeromq', "
                "'both', 'ssh', or 'none' not '{}'".format(self.salt_transport)
            )

        # Setup our property functions after class initialization and
        # after parsing the command line since most are set to None
        # ATTENTION: This should be the last step before returning the args or
        # some of the requirements won't be correctly set
        for funcname in dir(self):
            if not funcname.startswith("_property_"):
                continue
            property_name = funcname.split("_property_", 1)[-1]
            setattr(self, property_name, getattr(self, funcname))

        return args

    # <---- Overridden Methods ---------------------------------------------------------------------------------------


# <---- Custom Distribution Class ------------------------------------------------------------------------------------


if __name__ == "__main__":
    setup(distclass=SaltDistribution)
