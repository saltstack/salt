import atexit
import contextlib
import logging
import os
import pathlib
import pprint
import re
import shutil
import tarfile
import textwrap
import time
from typing import TYPE_CHECKING, Any, Dict, List
from zipfile import ZipFile

import attr
import distro
import packaging
import psutil
import pytest
import requests
from pytestshellutils.shell import DaemonImpl, Subprocess
from pytestshellutils.utils.processes import (
    ProcessResult,
    _get_cmdline,
    terminate_process,
)
from pytestskipmarkers.utils import platform
from saltfactories.bases import SystemdSaltDaemonImpl
from saltfactories.cli import call, key, salt
from saltfactories.daemons import api, master, minion
from saltfactories.utils import cli_scripts

try:
    import crypt

    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False
try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False

try:
    import winreg

    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

TESTS_DIR = pathlib.Path(__file__).resolve().parent.parent
CODE_DIR = TESTS_DIR.parent
ARTIFACTS_DIR = CODE_DIR / "artifacts"

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltPkgInstall:
    conf_dir: pathlib.Path = attr.ib()
    system_service: bool = attr.ib(default=False)
    proc: Subprocess = attr.ib(init=False)
    pkgs: List[str] = attr.ib(factory=list)
    onedir: bool = attr.ib(default=False)
    singlebin: bool = attr.ib(default=False)
    compressed: bool = attr.ib(default=False)
    hashes: Dict[str, Dict[str, Any]] = attr.ib()
    root: pathlib.Path = attr.ib(default=None)
    run_root: pathlib.Path = attr.ib(default=None)
    ssm_bin: pathlib.Path = attr.ib(default=None)
    bin_dir: pathlib.Path = attr.ib(default=None)
    # The artifact is an installer (exe, msi, pkg, rpm, deb)
    installer_pkg: bool = attr.ib(default=False)
    upgrade: bool = attr.ib(default=False)
    # install salt or not. This allows someone
    # to test a currently installed version of salt
    no_install: bool = attr.ib(default=False)
    no_uninstall: bool = attr.ib(default=False)

    distro_id: str = attr.ib(init=False)
    distro_codename: str = attr.ib(init=False)
    distro_name: str = attr.ib(init=False)
    distro_version: str = attr.ib(init=False)
    pkg_mngr: str = attr.ib(init=False)
    rm_pkg: str = attr.ib(init=False)
    salt_pkgs: List[str] = attr.ib(init=False)
    install_dir: pathlib.Path = attr.ib(init=False)
    binary_paths: Dict[str, List[pathlib.Path]] = attr.ib(init=False)
    classic: bool = attr.ib(default=False)
    prev_version: str = attr.ib()
    pkg_version: str = attr.ib(default="1")
    repo_data: str = attr.ib(init=False)
    major: str = attr.ib(init=False)
    minor: str = attr.ib(init=False)
    relenv: bool = attr.ib(default=True)
    file_ext: bool = attr.ib(default=None)

    @proc.default
    def _default_proc(self):
        return Subprocess()

    @hashes.default
    def _default_hashes(self):
        return {
            "BLAKE2B": {"file": None, "tool": "-blake2b512"},
            "SHA3_512": {"file": None, "tool": "-sha3-512"},
            "SHA512": {"file": None, "tool": "-sha512"},
        }

    @distro_id.default
    def _default_distro_id(self):
        return distro.id().lower()

    @distro_codename.default
    def _default_distro_codename(self):
        return distro.codename().lower()

    @distro_name.default
    def _default_distro_name(self):
        if distro.name():
            return distro.name().split()[0].lower()

    @distro_version.default
    def _default_distro_version(self):
        return distro.version().lower()

    @pkg_mngr.default
    def _default_pkg_mngr(self):
        if self.distro_id in ("centos", "redhat", "amzn", "fedora"):
            return "yum"
        elif self.distro_id in ("ubuntu", "debian"):
            ret = self.proc.run("apt-get", "update")
            self._check_retcode(ret)
            return "apt-get"

    @rm_pkg.default
    def _default_rm_pkg(self):
        if self.distro_id in ("centos", "redhat", "amzn", "fedora"):
            return "remove"
        elif self.distro_id in ("ubuntu", "debian"):
            return "purge"

    @salt_pkgs.default
    def _default_salt_pkgs(self):
        salt_pkgs = [
            "salt-api",
            "salt-syndic",
            "salt-ssh",
            "salt-master",
            "salt-cloud",
            "salt-minion",
        ]
        if self.distro_id in ("centos", "redhat", "amzn", "fedora"):
            salt_pkgs.append("salt")
        elif self.distro_id in ("ubuntu", "debian"):
            salt_pkgs.append("salt-common")
        return salt_pkgs

    @install_dir.default
    def _default_install_dir(self):
        if platform.is_windows():
            install_dir = pathlib.Path(
                os.getenv("ProgramFiles"), "Salt Project", "Salt"
            ).resolve()
        elif platform.is_darwin():
            # TODO: Add mac install dir path
            install_dir = pathlib.Path("/opt", "salt")
        else:
            install_dir = pathlib.Path("/opt", "saltstack", "salt")
        return install_dir

    @repo_data.default
    def _default_repo_data(self):
        """
        Query to see the published Salt artifacts
        from repo.json
        """
        url = "https://repo.saltproject.io/salt/onedir/repo.json"
        ret = requests.get(url)
        data = ret.json()
        return data

    def check_relenv(self, version):
        """
        Detects if we are using relenv
        onedir build
        """
        relenv = False
        if packaging.version.parse(version) >= packaging.version.parse("3006.0"):
            relenv = True
        return relenv

    def update_process_path(self):
        # The installer updates the path for the system, but that doesn't
        # make it to this python session, so we need to update that
        os.environ["PATH"] = ";".join([str(self.install_dir), os.getenv("path")])

        # When the MSI installer is run from self.proc.run, it doesn't update
        # the registry. When run from a normal command prompt it does. Until we
        # figure that out, we will update the process path as above. This
        # doesn't really check that the path is being set though... but I see
        # no other way around this
        # if HAS_WINREG:
        #     log.debug("Refreshing the path")
        #     # Get the updated system path from the registry
        #     path_key = winreg.OpenKeyEx(
        #         winreg.HKEY_LOCAL_MACHINE,
        #         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        #     )
        #     current_path = winreg.QueryValueEx(path_key, "path")[0]
        #     path_key.Close()
        #     # Update the path for the current running process
        #     os.environ["PATH"] = current_path

    def get_version(self, version_only=False):
        """
        Return the version information
        needed to install a previous version
        of Salt.
        """
        prev_version = self.prev_version
        pkg_version = None
        if not self.upgrade:
            # working with local artifact
            version = ""
            for artifact in ARTIFACTS_DIR.glob("**/*.*"):
                version = re.search(
                    r"([0-9].*)(\-[0-9].fc|\-[0-9].el|\+ds|\_all|\_any|\_amd64|\_arm64|\-[0-9].am|(\-[0-9]-[a-z]*-[a-z]*[0-9_]*.|\-[0-9]*.*)(tar.gz|tar.xz|zip|exe|msi|pkg|rpm|deb))",
                    artifact.name,
                )
                if version:
                    version = version.groups()[0].replace("_", "-").replace("~", "")
                    version = version.split("-")[0]
                    # TODO: Remove this clause.  This is to handle a versioning difficulty between pre-3006
                    # dev versions and older salt versions on deb-based distros
                    if version.startswith("1:"):
                        version = version[2:]
                    break
            major, minor = version.split(".", 1)
        else:
            if not prev_version:
                # We did not pass in a version, lets detect the latest
                # version information of a Salt artifact.
                latest = list(self.repo_data["latest"].keys())[0]
                version = self.repo_data["latest"][latest]["version"]
                if "-" in version:
                    prev_version, pkg_version = version.split("-")
                else:
                    prev_version, pkg_version = version, None
            else:
                # We passed in a version, but lets check if the pkg_version
                # is defined. Relenv pkgs do not define a pkg build number
                if "-" not in prev_version and not self.check_relenv(
                    version=prev_version
                ):
                    pkg_numbers = [
                        x for x in self.repo_data.keys() if prev_version in x
                    ]
                    pkg_version = 1
                    for number in pkg_numbers:
                        number = int(number.split("-")[1])
                        if number > pkg_version:
                            pkg_version = number
            major, minor = prev_version.split(".")
        if version_only:
            return version
        return major, minor, prev_version, pkg_version

    def __attrs_post_init__(self):
        self.major, self.minor, self.prev_version, self.pkg_version = self.get_version()
        self.relenv = self.check_relenv(self.major)
        file_ext_re = r"tar\.gz"
        if platform.is_darwin():
            file_ext_re = r"tar\.gz|pkg"
        if platform.is_windows():
            file_ext_re = "zip|exe|msi"
        for f_path in ARTIFACTS_DIR.glob("**/*.*"):
            f_path = str(f_path)
            if re.search(f"salt-(.*).({file_ext_re})$", f_path, re.IGNORECASE):
                # Compressed can be zip, tar.gz, exe, or pkg. All others are
                # deb and rpm
                self.compressed = True
                self.file_ext = os.path.splitext(f_path)[1].strip(".")
                if self.file_ext == "gz":
                    if f_path.endswith("tar.gz"):
                        self.file_ext = "tar.gz"
                self.pkgs.append(f_path)
                if platform.is_windows():
                    self.root = pathlib.Path(os.getenv("LocalAppData")).resolve()
                    if self.file_ext == "zip":
                        with ZipFile(f_path, "r") as zip:
                            first = zip.infolist()[0]
                            if first.filename == "salt/ssm.exe":
                                self.onedir = True
                                self.bin_dir = self.root / "salt" / "salt"
                                self.run_root = self.bin_dir / "salt.exe"
                                self.ssm_bin = self.root / "salt" / "ssm.exe"
                            elif first.filename == "salt.exe":
                                self.singlebin = True
                                self.run_root = self.root / "salt.exe"
                                self.ssm_bin = self.root / "ssm.exe"
                            else:
                                log.error(
                                    "Unexpected archive layout. First: %s",
                                    first.filename,
                                )
                    elif self.file_ext in ["exe", "msi"]:
                        self.compressed = False
                        self.onedir = True
                        self.installer_pkg = True
                        self.root = self.install_dir.parent
                        self.bin_dir = self.install_dir
                        self.ssm_bin = self.install_dir / "ssm.exe"
                    else:
                        log.error("Unexpected file extension: %s", self.file_ext)
                else:
                    if platform.is_darwin():
                        self.root = pathlib.Path(os.sep, "opt")
                    else:
                        self.root = pathlib.Path(os.sep, "usr", "local", "bin")

                    if self.file_ext == "pkg":
                        self.compressed = False
                        self.onedir = True
                        self.installer_pkg = True
                        self.bin_dir = self.root / "salt" / "bin"
                        self.run_root = self.bin_dir / "run"
                    elif self.file_ext == "tar.gz":
                        with tarfile.open(f_path) as tar:
                            # The first item will be called salt
                            first = next(iter(tar.getmembers()))
                            if first.name == "salt" and first.isdir():
                                self.onedir = True
                                self.bin_dir = self.root / "salt" / "run"
                                self.run_root = self.bin_dir / "run"
                            elif first.name == "salt" and first.isfile():
                                self.singlebin = True
                                self.run_root = self.root / "salt"
                            else:
                                log.error(
                                    "Unexpected archive layout. First: %s (isdir: %s, isfile: %s)",
                                    first.name,
                                    first.isdir(),
                                    first.isfile(),
                                )
                    else:
                        log.error("Unexpected file extension: %s", self.file_ext)

            if re.search(
                r"salt(.*)(x86_64|all|amd64|aarch64|arm64)\.(rpm|deb)$", f_path
            ):
                self.installer_pkg = True
                self.pkgs.append(f_path)

        if not self.pkgs:
            pytest.fail("Could not find Salt Artifacts")

        python_bin = self.install_dir / "bin" / "python3"
        if platform.is_windows():
            python_bin = self.install_dir / "Scripts" / "python.exe"
        if not self.compressed:
            if platform.is_windows():
                self.binary_paths = {
                    "call": ["salt-call.exe"],
                    "cp": ["salt-cp.exe"],
                    "minion": ["salt-minion.exe"],
                    "pip": ["salt-pip.exe"],
                    "python": [python_bin],
                }
            else:
                if os.path.exists(self.install_dir / "bin" / "salt"):
                    install_dir = self.install_dir / "bin"
                else:
                    install_dir = self.install_dir
                self.binary_paths = {
                    "salt": [install_dir / "salt"],
                    "api": [install_dir / "salt-api"],
                    "call": [install_dir / "salt-call"],
                    "cloud": [install_dir / "salt-cloud"],
                    "cp": [install_dir / "salt-cp"],
                    "key": [install_dir / "salt-key"],
                    "master": [install_dir / "salt-master"],
                    "minion": [install_dir / "salt-minion"],
                    "proxy": [install_dir / "salt-proxy"],
                    "run": [install_dir / "salt-run"],
                    "ssh": [install_dir / "salt-ssh"],
                    "syndic": [install_dir / "salt-syndic"],
                    "spm": [install_dir / "spm"],
                    "pip": [install_dir / "salt-pip"],
                    "python": [python_bin],
                }
        else:
            if self.run_root and os.path.exists(self.run_root):
                if platform.is_windows():
                    self.binary_paths = {
                        "call": [str(self.run_root), "call"],
                        "cp": [str(self.run_root), "cp"],
                        "minion": [str(self.run_root), "minion"],
                        "pip": [str(self.run_root), "pip"],
                        "python": [python_bin],
                    }
                else:
                    self.binary_paths = {
                        "salt": [str(self.run_root)],
                        "api": [str(self.run_root), "api"],
                        "call": [str(self.run_root), "call"],
                        "cloud": [str(self.run_root), "cloud"],
                        "cp": [str(self.run_root), "cp"],
                        "key": [str(self.run_root), "key"],
                        "master": [str(self.run_root), "master"],
                        "minion": [str(self.run_root), "minion"],
                        "proxy": [str(self.run_root), "proxy"],
                        "run": [str(self.run_root), "run"],
                        "ssh": [str(self.run_root), "ssh"],
                        "syndic": [str(self.run_root), "syndic"],
                        "spm": [str(self.run_root), "spm"],
                        "pip": [str(self.run_root), "pip"],
                        "python": [python_bin],
                    }
            else:
                if platform.is_windows():
                    self.binary_paths = {
                        "call": [self.install_dir / "salt-call.exe"],
                        "cp": [self.install_dir / "salt-cp.exe"],
                        "minion": [self.install_dir / "salt-minion.exe"],
                        "pip": [self.install_dir / "salt-pip.exe"],
                        "python": [python_bin],
                    }
                else:
                    self.binary_paths = {
                        "salt": [self.install_dir / "salt"],
                        "api": [self.install_dir / "salt-api"],
                        "call": [self.install_dir / "salt-call"],
                        "cloud": [self.install_dir / "salt-cloud"],
                        "cp": [self.install_dir / "salt-cp"],
                        "key": [self.install_dir / "salt-key"],
                        "master": [self.install_dir / "salt-master"],
                        "minion": [self.install_dir / "salt-minion"],
                        "proxy": [self.install_dir / "salt-proxy"],
                        "run": [self.install_dir / "salt-run"],
                        "ssh": [self.install_dir / "salt-ssh"],
                        "syndic": [self.install_dir / "salt-syndic"],
                        "spm": [self.install_dir / "spm"],
                        "pip": [self.install_dir / "salt-pip"],
                        "python": [python_bin],
                    }

    @staticmethod
    def salt_factories_root_dir(system_service: bool = False) -> pathlib.Path:
        if system_service is False:
            return None
        if platform.is_windows():
            return pathlib.Path("C:/salt")
        if platform.is_darwin():
            return pathlib.Path("/opt/salt")
        return pathlib.Path("/")

    def _check_retcode(self, ret):
        """
        helper function ot check subprocess.run
        returncode equals 0, if not raise assertionerror
        """
        if ret.returncode != 0:
            log.error(ret)
        assert ret.returncode == 0
        return True

    @property
    def salt_hashes(self):
        for _hash in self.hashes.keys():
            for fpath in ARTIFACTS_DIR.glob(f"**/*{_hash}*"):
                fpath = str(fpath)
                if re.search(f"{_hash}", fpath):
                    self.hashes[_hash]["file"] = fpath

        return self.hashes

    def _install_ssm_service(self):
        # Register the services
        # run_root and ssm_bin are configured in helper.py to point to the
        # correct binary location
        log.debug("Installing master service")
        ret = self.proc.run(
            str(self.ssm_bin),
            "install",
            "salt-master",
            str(self.run_root),
            "master",
            "-c",
            str(self.conf_dir),
        )
        self._check_retcode(ret)
        log.debug("Installing minion service")
        ret = self.proc.run(
            str(self.ssm_bin),
            "install",
            "salt-minion",
            str(self.run_root),
            "minion",
            "-c",
            str(self.conf_dir),
        )
        self._check_retcode(ret)
        log.debug("Installing api service")
        ret = self.proc.run(
            str(self.ssm_bin),
            "install",
            "salt-api",
            str(self.run_root),
            "api",
            "-c",
            str(self.conf_dir),
        )
        self._check_retcode(ret)

    def _install_compressed(self, upgrade=False):
        pkg = self.pkgs[0]
        log.info("Installing %s", pkg)
        if platform.is_windows():
            if pkg.endswith("zip"):
                # Extract the files
                log.debug("Extracting zip file")
                with ZipFile(pkg, "r") as zip:
                    zip.extractall(path=self.root)
            elif pkg.endswith("exe") or pkg.endswith("msi"):
                log.error("Not a compressed package type: %s", pkg)
            else:
                log.error("Unknown package type: %s", pkg)
            if self.system_service:
                self._install_ssm_service()
        elif platform.is_darwin():
            log.debug("Extracting tarball into %s", self.root)
            with tarfile.open(pkg) as tar:  # , "r:gz")
                tar.extractall(path=str(self.root))
        else:
            log.debug("Extracting tarball into %s", self.root)
            with tarfile.open(pkg) as tar:  # , "r:gz")
                tar.extractall(path=str(self.root))

    def _install_pkgs(self, upgrade=False):
        pkg = self.pkgs[0]
        if platform.is_windows():
            if upgrade:
                self.root = self.install_dir.parent
                self.bin_dir = self.install_dir
                self.ssm_bin = self.install_dir / "ssm.exe"
            if pkg.endswith("exe"):
                # Install the package
                log.debug("Installing: %s", str(pkg))
                ret = self.proc.run(str(pkg), "/start-minion=0", "/S")
                self._check_retcode(ret)
            elif pkg.endswith("msi"):
                # Install the package
                log.debug("Installing: %s", str(pkg))
                # START_MINION="" does not work as documented. The service is
                # still starting. We need to fix this for RC2
                ret = self.proc.run(
                    "msiexec.exe", "/qn", "/i", str(pkg), 'START_MINION=""'
                )
                self._check_retcode(ret)
            else:
                log.error("Invalid package: %s", pkg)
                return False

            # Stop the service installed by the installer. We only need this
            # until we fix the issue where the MSI installer is starting the
            # salt-minion service when it shouldn't
            log.debug("Removing installed salt-minion service")
            self.proc.run(str(self.ssm_bin), "stop", "salt-minion")

            # Remove the service installed by the installer
            log.debug("Removing installed salt-minion service")
            self.proc.run(str(self.ssm_bin), "remove", "salt-minion", "confirm")
            self.update_process_path()

        elif platform.is_darwin():
            daemons_dir = pathlib.Path(os.sep, "Library", "LaunchDaemons")
            service_name = "com.saltstack.salt.minion"
            plist_file = daemons_dir / f"{service_name}.plist"
            log.debug("Installing: %s", str(pkg))
            ret = self.proc.run("installer", "-pkg", str(pkg), "-target", "/")
            self._check_retcode(ret)
            # Stop the service installed by the installer
            self.proc.run("launchctl", "disable", f"system/{service_name}")
            self.proc.run("launchctl", "bootout", "system", str(plist_file))
        elif upgrade:
            log.info("Installing packages:\n%s", pprint.pformat(self.pkgs))
            ret = self.proc.run(self.pkg_mngr, "upgrade", "-y", *self.pkgs)
        else:
            log.info("Installing packages:\n%s", pprint.pformat(self.pkgs))
            ret = self.proc.run(self.pkg_mngr, "install", "-y", *self.pkgs)
        log.info(ret)
        self._check_retcode(ret)

    def install(self, upgrade=False):
        if self.compressed:
            self._install_compressed(upgrade=upgrade)
        else:
            self._install_pkgs(upgrade=upgrade)
            if self.distro_id in ("ubuntu", "debian"):
                self.stop_services()

    def stop_services(self):
        """
        Debian distros automatically start the services
        We want to ensure our tests start with the config
        settings we have set. This will also verify the expected
        services are up and running.
        """
        for service in ["salt-syndic", "salt-master", "salt-minion"]:
            check_run = self.proc.run("systemctl", "status", service)
            if check_run.returncode != 0:
                # The system was not started automatically and we
                # are expecting it to be on install
                log.debug("The service %s was not started on install.", service)
                return False
            stop_service = self.proc.run("systemctl", "stop", service)
            self._check_retcode(stop_service)
        return True

    def install_previous(self):
        """
        Install previous version. This is used for
        upgrade tests.
        """
        major_ver = self.major
        minor_ver = self.minor
        pkg_version = self.pkg_version
        full_version = f"{self.major}.{self.minor}-{pkg_version}"

        min_ver = f"{major_ver}"
        distro_name = self.distro_name
        if distro_name == "centos" or distro_name == "fedora":
            distro_name = "redhat"
        root_url = "salt/py3/"
        if self.classic:
            root_url = "py3/"

        if self.distro_name in ["redhat", "centos", "amazon", "fedora"]:
            for fp in pathlib.Path("/etc", "yum.repos.d").glob("epel*"):
                fp.unlink()
            gpg_key = "SALTSTACK-GPG-KEY.pub"
            if self.distro_version == "9":
                gpg_key = "SALTSTACK-GPG-KEY2.pub"
            if platform.is_aarch64():
                arch = "aarch64"
            else:
                arch = "x86_64"
            ret = self.proc.run(
                "rpm",
                "--import",
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}/{gpg_key}",
            )
            self._check_retcode(ret)
            ret = self.proc.run(
                "curl",
                "-fsSL",
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}.repo",
                "-o",
                f"/etc/yum.repos.d/salt-{distro_name}.repo",
            )
            self._check_retcode(ret)
            ret = self.proc.run(self.pkg_mngr, "clean", "expire-cache")
            self._check_retcode(ret)
            ret = self.proc.run(
                self.pkg_mngr,
                "install",
                *self.salt_pkgs,
                "-y",
            )
            self._check_retcode(ret)

        elif distro_name in ["debian", "ubuntu"]:
            ret = self.proc.run(self.pkg_mngr, "install", "curl", "-y")
            self._check_retcode(ret)
            ret = self.proc.run(self.pkg_mngr, "install", "apt-transport-https", "-y")
            self._check_retcode(ret)
            ## only classic 3005 has arm64 support
            if self.major >= "3006" and platform.is_aarch64():
                arch = "arm64"
            elif platform.is_aarch64() and self.classic:
                arch = "arm64"
            else:
                arch = "amd64"
            pathlib.Path("/etc/apt/keyrings").mkdir(parents=True, exist_ok=True)
            ret = self.proc.run(
                "curl",
                "-fsSL",
                "-o",
                "/etc/apt/keyrings/salt-archive-keyring.gpg",
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}/salt-archive-keyring.gpg",
            )
            self._check_retcode(ret)
            with open(
                pathlib.Path("/etc", "apt", "sources.list.d", "salt.list"), "w"
            ) as fp:
                fp.write(
                    f"deb [signed-by=/etc/apt/keyrings/salt-archive-keyring.gpg arch={arch}] "
                    f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver} {self.distro_codename} main"
                )
            ret = self.proc.run(self.pkg_mngr, "update")
            self._check_retcode(ret)
            ret = self.proc.run(
                self.pkg_mngr,
                "install",
                *self.salt_pkgs,
                "-y",
            )
            self._check_retcode(ret)
            self.stop_services()
        elif platform.is_windows():
            self.onedir = True
            self.installer_pkg = True
            self.bin_dir = self.install_dir / "bin"
            self.run_root = self.bin_dir / f"salt.exe"
            self.ssm_bin = self.bin_dir / "ssm.exe"
            if self.file_ext == "msi":
                self.ssm_bin = self.install_dir / "ssm.exe"

            if not self.classic:
                win_pkg = f"salt-{full_version}-windows-amd64.{self.file_ext}"
                win_pkg_url = f"https://repo.saltproject.io/salt/py3/windows/{full_version}/{win_pkg}"
            else:
                if self.file_ext == "msi":
                    win_pkg = f"Salt-Minion-{min_ver}-1-Py3-AMD64.{self.file_ext}"
                elif self.file_ext == "exe":
                    win_pkg = f"Salt-Minion-{min_ver}-1-Py3-AMD64-Setup.{self.file_ext}"
                win_pkg_url = f"https://repo.saltproject.io/windows/{win_pkg}"
            pkg_path = pathlib.Path(r"C:\TEMP", win_pkg)
            pkg_path.parent.mkdir(exist_ok=True)
            ret = requests.get(win_pkg_url)

            with open(pkg_path, "wb") as fp:
                fp.write(ret.content)
            if self.file_ext == "msi":
                ret = self.proc.run(
                    "msiexec.exe", "/qn", "/i", str(pkg_path), 'START_MINION=""'
                )
                self._check_retcode(ret)
            else:
                ret = self.proc.run(pkg_path, "/start-minion=0", "/S")
                self._check_retcode(ret)

            # Stop the service installed by the installer
            log.debug("Removing installed salt-minion service")
            self.proc.run(str(self.ssm_bin), "stop", "salt-minion")

            log.debug("Removing installed salt-minion service")
            ret = self.proc.run(str(self.ssm_bin), "remove", "salt-minion", "confirm")
            self._check_retcode(ret)

            if self.system_service:
                self._install_system_service()

        elif platform.is_darwin():
            if self.classic:
                mac_pkg = f"salt-{min_ver}.{minor_ver}-1-py3-x86_64.pkg"
                mac_pkg_url = f"https://repo.saltproject.io/osx/{mac_pkg}"
            else:
                mac_pkg = f"salt-{min_ver}.{minor_ver}-1-macos-x86_64.pkg"
                mac_pkg_url = f"https://repo.saltproject.io/salt/py3/macos/{major_ver}.{minor_ver}-1/{mac_pkg}"
            mac_pkg_path = f"/tmp/{mac_pkg}"
            if not os.path.exists(mac_pkg_path):
                ret = self.proc.run(
                    "curl",
                    "-fsSL",
                    "-o",
                    f"/tmp/{mac_pkg}",
                    f"{mac_pkg_url}",
                )
                self._check_retcode(ret)

            ret = self.proc.run("installer", "-pkg", mac_pkg_path, "-target", "/")
            self._check_retcode(ret)

    def _uninstall_compressed(self):
        if platform.is_windows():
            if self.system_service:
                # Uninstall the services
                log.debug("Uninstalling master service")
                self.proc.run(str(self.ssm_bin), "stop", "salt-master")
                self.proc.run(str(self.ssm_bin), "remove", "salt-master", "confirm")
                log.debug("Uninstalling minion service")
                self.proc.run(str(self.ssm_bin), "stop", "salt-minion")
                self.proc.run(str(self.ssm_bin), "remove", "salt-minion", "confirm")
                log.debug("Uninstalling api service")
                self.proc.run(str(self.ssm_bin), "stop", "salt-api")
                self.proc.run(str(self.ssm_bin), "remove", "salt-api", "confirm")
            log.debug("Removing the Salt Service Manager")
            if self.ssm_bin:
                try:
                    self.ssm_bin.unlink()
                except PermissionError:
                    atexit.register(self.ssm_bin.unlink)
        if platform.is_darwin():
            # From here: https://stackoverflow.com/a/46118276/4581998
            daemons_dir = pathlib.Path(os.sep, "Library", "LaunchDaemons")
            for service in ("minion", "master", "api", "syndic"):
                service_name = f"com.saltstack.salt.{service}"
                plist_file = daemons_dir / f"{service_name}.plist"
                # Stop the services
                self.proc.run("launchctl", "disable", f"system/{service_name}")
                self.proc.run("launchctl", "bootout", "system", str(plist_file))

            # Remove Symlink to salt-config
            if os.path.exists("/usr/local/sbin/salt-config"):
                os.unlink("/usr/local/sbin/salt-config")

            # Remove supporting files
            self.proc.run(
                "pkgutil",
                "--only-files",
                "--files",
                "com.saltstack.salt",
                "|",
                "grep",
                "-v",
                "opt",
                "|",
                "tr",
                "'\n'",
                "' '",
                "|",
                "xargs",
                "-0",
                "rm",
                "-f",
            )

            # Remove directories
            if os.path.exists("/etc/salt"):
                shutil.rmtree("/etc/salt")

            # Remove path
            if os.path.exists("/etc/paths.d/salt"):
                os.remove("/etc/paths.d/salt")

            # Remove receipt
            self.proc.run("pkgutil", "--forget", "com.saltstack.salt")

        if self.singlebin:
            log.debug("Deleting the salt binary: %s", self.run_root)
            if self.run_root:
                try:
                    self.run_root.unlink()
                except PermissionError:
                    atexit.register(self.run_root.unlink)
        else:
            log.debug("Deleting the onedir directory: %s", self.root / "salt")
            shutil.rmtree(str(self.root / "salt"))

    def _uninstall_pkgs(self):
        pkg = self.pkgs[0]
        if platform.is_windows():
            log.info("Uninstalling %s", pkg)
            if pkg.endswith("exe"):
                uninst = self.install_dir / "uninst.exe"
                ret = self.proc.run(uninst, "/S")
                self._check_retcode(ret)
            elif pkg.endswith("msi"):
                ret = self.proc.run("msiexec.exe", "/qn", "/x", pkg)
                self._check_retcode(ret)

        elif platform.is_darwin():
            self._uninstall_compressed()
        else:
            log.debug("Un-Installing packages:\n%s", pprint.pformat(self.salt_pkgs))
            ret = self.proc.run(self.pkg_mngr, self.rm_pkg, "-y", *self.salt_pkgs)
            self._check_retcode(ret)

    def uninstall(self):
        if self.compressed:
            self._uninstall_compressed()
        else:
            self._uninstall_pkgs()

    def assert_uninstalled(self):
        """
        Assert that the paths in /opt/saltstack/ were correctly
        removed or not removed
        """
        return
        if platform.is_windows():
            # I'm not sure where the /opt/saltstack path is coming from
            # This is the path we're using to test windows
            opt_path = pathlib.Path(os.getenv("LocalAppData"), "salt", "pypath")
        else:
            opt_path = pathlib.Path(os.sep, "opt", "saltstack", "salt", "pypath")
        if not opt_path.exists():
            if platform.is_windows():
                assert not opt_path.parent.exists()
            else:
                assert not opt_path.parent.parent.exists()
        else:
            opt_path_contents = list(opt_path.rglob("*"))
            if not opt_path_contents:
                pytest.fail(
                    f"The path '{opt_path}' exists but there are no files in it."
                )
            else:
                for path in list(opt_path_contents):
                    if path.name in (".installs.json", "__pycache__"):
                        opt_path_contents.remove(path)
                if opt_path_contents:
                    pytest.fail(
                        "The test left some files behind: {}".format(
                            ", ".join([str(p) for p in opt_path_contents])
                        )
                    )

    def write_launchd_conf(self, service):
        service_name = f"com.saltstack.salt.{service}"
        ret = self.proc.run("launchctl", "list", service_name)
        # 113 means it couldn't find a service with that name
        if ret.returncode == 113:
            daemons_dir = pathlib.Path(os.sep, "Library", "LaunchDaemons")
            plist_file = daemons_dir / f"{service_name}.plist"
            # Make sure we're using this plist file
            if plist_file.exists():
                log.warning("Removing existing plist file for service: %s", service)
                plist_file.unlink()

            log.debug("Creating plist file for service: %s", service)
            contents = textwrap.dedent(
                f"""\
                <?xml version="1.0" encoding="UTF-8"?>
                <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
                <plist version="1.0">
                    <dict>
                        <key>Label</key>
                        <string>{service_name}</string>
                        <key>RunAtLoad</key>
                        <true/>
                        <key>KeepAlive</key>
                        <true/>
                        <key>ProgramArguments</key>
                        <array>
                            <string>{self.run_root}</string>
                            <string>{service}</string>
                            <string>-c</string>
                            <string>{self.conf_dir}</string>
                        </array>
                        <key>SoftResourceLimits</key>
                        <dict>
                            <key>NumberOfFiles</key>
                            <integer>100000</integer>
                        </dict>
                        <key>HardResourceLimits</key>
                        <dict>
                            <key>NumberOfFiles</key>
                            <integer>100000</integer>
                        </dict>
                    </dict>
                </plist>
                """
            )
            plist_file.write_text(contents, encoding="utf-8")
            contents = plist_file.read_text()
            log.debug("Created '%s'. Contents:\n%s", plist_file, contents)

            # Delete the plist file upon completion
            atexit.register(plist_file.unlink)

    def write_systemd_conf(self, service, binary):
        ret = self.proc.run("systemctl", "daemon-reload")
        self._check_retcode(ret)
        ret = self.proc.run("systemctl", "status", service)
        if ret.returncode in (3, 4):
            log.warning(
                "No systemd unit file was found for service %s. Creating one.", service
            )
            contents = textwrap.dedent(
                """\
                [Unit]
                Description={service}

                [Service]
                KillMode=process
                Type=notify
                NotifyAccess=all
                LimitNOFILE=8192
                ExecStart={tgt} -c {conf_dir}

                [Install]
                WantedBy=multi-user.target
                """
            )
            if isinstance(binary, list) and len(binary) == 1:
                binary = shutil.which(binary[0]) or binary[0]
            elif isinstance(binary, list):
                binary = " ".join(binary)
            unit_path = pathlib.Path(
                os.sep, "etc", "systemd", "system", f"{service}.service"
            )
            contents = contents.format(
                service=service, tgt=binary, conf_dir=self.conf_dir
            )
            log.info("Created '%s'. Contents:\n%s", unit_path, contents)
            unit_path.write_text(contents, encoding="utf-8")
            ret = self.proc.run("systemctl", "daemon-reload")
            atexit.register(unit_path.unlink)
            self._check_retcode(ret)

    def __enter__(self):
        if platform.is_windows():
            self.update_process_path()

        if not self.no_install:
            if self.upgrade:
                self.install_previous()
            else:
                self.install()
        return self

    def __exit__(self, *_):
        if not self.no_uninstall:
            self.uninstall()
            self.assert_uninstalled()


class PkgSystemdSaltDaemonImpl(SystemdSaltDaemonImpl):
    def get_service_name(self):
        if self._service_name is None:
            self._service_name = self.factory.script_name
        return self._service_name


@attr.s(kw_only=True)
class PkgLaunchdSaltDaemonImpl(PkgSystemdSaltDaemonImpl):

    plist_file = attr.ib()

    @plist_file.default
    def _default_plist_file(self):
        daemons_dir = pathlib.Path(os.sep, "Library", "LaunchDaemons")
        return daemons_dir / f"{self.get_service_name()}.plist"

    def get_service_name(self):
        if self._service_name is None:
            service_name = super().get_service_name()
            if "-" in service_name:
                service_name = service_name.split("-")[-1]
            self._service_name = f"com.saltstack.salt.{service_name}"
        return self._service_name

    def cmdline(self, *args):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
            Additional arguments to use when starting the subprocess

        """
        if args:  # pragma: no cover
            log.debug(
                "%s.run() is ignoring the passed in arguments: %r",
                self.__class__.__name__,
                args,
            )
        self._internal_run(
            "launchctl",
            "enable",
            f"system/{self.get_service_name()}",
        )
        return (
            "launchctl",
            "bootstrap",
            "system",
            str(self.plist_file),
        )

    def is_running(self):
        """
        Returns true if the sub-process is alive.
        """
        if self._process is None:
            ret = self._internal_run("launchctl", "list", self.get_service_name())
            if ret.stdout == "":
                return False

            if "PID" not in ret.stdout:
                return False

            pid = None
            # PID in a line that looks like this
            # "PID" = 445;
            for line in ret.stdout.splitlines():
                if "PID" in line:
                    pid = line.rstrip(";").split(" = ")[1]

            if pid is None:
                return False

            self._process = psutil.Process(int(pid))

        return self._process.is_running()

    def _terminate(self):
        """
        This method actually terminates the started daemon.
        """
        # We completely override the parent class method because we're not using
        # the self._terminal property, it's a launchd service
        if self._process is None:  # pragma: no cover
            if TYPE_CHECKING:
                # Make mypy happy
                assert self._terminal_result
            return (
                self._terminal_result
            )  # pylint: disable=access-member-before-definition

        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        pid = self.pid
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(pid).children(recursive=True):
                if (
                    child not in self._children
                ):  # pylint: disable=access-member-before-definition
                    self._children.append(
                        child
                    )  # pylint: disable=access-member-before-definition

        if self._process.is_running():  # pragma: no cover
            cmdline = _get_cmdline(self._process)
        else:
            cmdline = []

        # Disable the service
        self._internal_run(
            "launchctl",
            "disable",
            f"system/{self.get_service_name()}",
        )
        # Unload the service
        self._internal_run("launchctl", "bootout", "system", str(self.plist_file))

        if self._process.is_running():  # pragma: no cover
            try:
                self._process.wait()
            except psutil.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait()
                except psutil.TimeoutExpired:
                    pass

        exitcode = self._process.wait() or 0

        # Dereference the internal _process attribute
        self._process = None
        # Lets log and kill any child processes left behind, including the main subprocess
        # if it failed to properly stop
        terminate_process(
            pid=pid,
            kill_children=True,
            children=self._children,  # pylint: disable=access-member-before-definition
            slow_stop=self.factory.slow_stop,
        )

        if self._terminal_stdout is not None:
            self._terminal_stdout.close()  # pylint: disable=access-member-before-definition
        if self._terminal_stderr is not None:
            self._terminal_stderr.close()  # pylint: disable=access-member-before-definition
        stdout = stderr = ""
        try:
            self._terminal_result = ProcessResult(
                returncode=exitcode, stdout=stdout, stderr=stderr, cmdline=cmdline
            )
            log.info("%s %s", self.factory.__class__.__name__, self._terminal_result)
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_stdout = None
            self._terminal_stderr = None
            self._terminal_timeout = None
            self._children = []


@attr.s(kw_only=True)
class PkgSsmSaltDaemonImpl(PkgSystemdSaltDaemonImpl):
    def cmdline(self, *args):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess.

        :param str args:
            Additional arguments to use when starting the subprocess

        """
        if args:  # pragma: no cover
            log.debug(
                "%s.run() is ignoring the passed in arguments: %r",
                self.__class__.__name__,
                args,
            )
        return (
            str(self.factory.salt_pkg_install.ssm_bin),
            "start",
            self.get_service_name(),
        )

    def is_running(self):
        """
        Returns true if the sub-process is alive.
        """
        if self._process is None:
            n = 1
            while True:
                if self._process is not None:
                    break
                time.sleep(1)
                ret = self._internal_run(
                    str(self.factory.salt_pkg_install.ssm_bin),
                    "processes",
                    self.get_service_name(),
                )
                log.warning(ret)
                if not ret.stdout or (ret.stdout and not ret.stdout.strip()):
                    if n >= 120:
                        return False
                    n += 1
                    continue
                for line in ret.stdout.splitlines():
                    log.warning("Line: %s", line)
                    if not line.strip():
                        continue
                    mainpid = line.strip().split()[0]
                    self._process = psutil.Process(int(mainpid))
                    break
        return self._process.is_running()

    def _terminate(self):
        """
        This method actually terminates the started daemon.
        """
        # We completely override the parent class method because we're not using the
        # self._terminal property, it's a systemd service
        if self._process is None:  # pragma: no cover
            if TYPE_CHECKING:
                # Make mypy happy
                assert self._terminal_result
            return (
                self._terminal_result
            )  # pylint: disable=access-member-before-definition

        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        pid = self.pid
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(pid).children(recursive=True):
                if (
                    child not in self._children
                ):  # pylint: disable=access-member-before-definition
                    self._children.append(
                        child
                    )  # pylint: disable=access-member-before-definition

        if self._process.is_running():  # pragma: no cover
            cmdline = _get_cmdline(self._process)
        else:
            cmdline = []

        # Tell ssm to stop the service
        try:
            self._internal_run(
                str(self.factory.salt_pkg_install.ssm_bin),
                "stop",
                self.get_service_name(),
            )
        except FileNotFoundError:
            pass

        if self._process.is_running():  # pragma: no cover
            try:
                self._process.wait()
            except psutil.TimeoutExpired:
                self._process.terminate()
                try:
                    self._process.wait()
                except psutil.TimeoutExpired:
                    pass

        exitcode = self._process.wait() or 0

        # Dereference the internal _process attribute
        self._process = None
        # Lets log and kill any child processes left behind, including the main subprocess
        # if it failed to properly stop
        terminate_process(
            pid=pid,
            kill_children=True,
            children=self._children,  # pylint: disable=access-member-before-definition
            slow_stop=self.factory.slow_stop,
        )

        if self._terminal_stdout is not None:
            self._terminal_stdout.close()  # pylint: disable=access-member-before-definition
        if self._terminal_stderr is not None:
            self._terminal_stderr.close()  # pylint: disable=access-member-before-definition
        stdout = stderr = ""
        try:
            self._terminal_result = ProcessResult(
                returncode=exitcode, stdout=stdout, stderr=stderr, cmdline=cmdline
            )
            log.info("%s %s", self.factory.__class__.__name__, self._terminal_result)
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_stdout = None
            self._terminal_stderr = None
            self._terminal_timeout = None
            self._children = []


@attr.s(kw_only=True)
class PkgMixin:
    salt_pkg_install: SaltPkgInstall = attr.ib()

    def get_script_path(self):
        if self.salt_pkg_install.compressed or (
            platform.is_darwin()
            and self.salt_pkg_install.classic
            and self.salt_pkg_install.upgrade
        ):
            if self.salt_pkg_install.run_root and os.path.exists(
                self.salt_pkg_install.run_root
            ):
                return str(self.salt_pkg_install.run_root)
            elif os.path.exists(self.salt_pkg_install.bin_dir / self.script_name):
                return str(self.salt_pkg_install.bin_dir / self.script_name)
            else:
                return str(self.salt_pkg_install.install_dir / self.script_name)
        return super().get_script_path()

    def get_base_script_args(self):
        base_script_args = []
        if self.salt_pkg_install.run_root and os.path.exists(
            self.salt_pkg_install.run_root
        ):
            if self.salt_pkg_install.compressed:
                if self.script_name == "spm":
                    base_script_args.append(self.script_name)
                elif self.script_name != "salt":
                    base_script_args.append(self.script_name.split("salt-")[-1])
        base_script_args.extend(super().get_base_script_args())
        return base_script_args

    def cmdline(self, *args, **kwargs):
        _cmdline = super().cmdline(*args, **kwargs)
        if self.salt_pkg_install.compressed is False:
            return _cmdline
        if _cmdline[0] == self.python_executable:
            _cmdline.pop(0)
        return _cmdline


@attr.s(kw_only=True)
class DaemonPkgMixin(PkgMixin):
    def __attrs_post_init__(self):
        if not platform.is_windows() and self.salt_pkg_install.system_service:
            if platform.is_darwin():
                self.write_launchd_conf()
            else:
                self.write_systemd_conf()

    def get_service_name(self):
        return self.script_name

    def write_launchd_conf(self):
        raise NotImplementedError

    def write_systemd_conf(self):
        raise NotImplementedError


@attr.s(kw_only=True)
class SaltMaster(DaemonPkgMixin, master.SaltMaster):
    """
    Subclassed just to tweak the binary paths if needed and factory classes.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt-master"
        master.SaltMaster.__attrs_post_init__(self)
        DaemonPkgMixin.__attrs_post_init__(self)

    def _get_impl_class(self):
        if self.system_install and self.salt_pkg_install.system_service:
            if platform.is_windows():
                return PkgSsmSaltDaemonImpl
            if platform.is_darwin():
                return PkgLaunchdSaltDaemonImpl
            return PkgSystemdSaltDaemonImpl
        return DaemonImpl

    def write_launchd_conf(self):
        self.salt_pkg_install.write_launchd_conf("master")

    def write_systemd_conf(self):
        self.salt_pkg_install.write_systemd_conf(
            "salt-master", self.salt_pkg_install.binary_paths["master"]
        )

    def salt_minion_daemon(self, minion_id, **kwargs):
        return super().salt_minion_daemon(
            minion_id,
            factory_class=SaltMinion,
            salt_pkg_install=self.salt_pkg_install,
            **kwargs,
        )

    def salt_api_daemon(self, **kwargs):
        return super().salt_api_daemon(
            factory_class=SaltApi, salt_pkg_install=self.salt_pkg_install, **kwargs
        )

    def salt_key_cli(self, **factory_class_kwargs):
        return super().salt_key_cli(
            factory_class=SaltKey,
            salt_pkg_install=self.salt_pkg_install,
            **factory_class_kwargs,
        )

    def salt_cli(self, **factory_class_kwargs):
        return super().salt_cli(
            factory_class=SaltCli,
            salt_pkg_install=self.salt_pkg_install,
            **factory_class_kwargs,
        )


@attr.s(kw_only=True)
class SaltMasterWindows(SaltMaster):
    """
    Subclassed just to tweak the binary paths if needed and factory classes.
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.script_name = cli_scripts.generate_script(
            bin_dir=self.factories_manager.scripts_dir,
            script_name="salt-master",
            code_dir=self.factories_manager.code_dir.parent,
        )

    def _get_impl_class(self):
        return DaemonImpl

    def cmdline(self, *args, **kwargs):
        cmdline_ = super().cmdline(*args, **kwargs)
        if self.python_executable:
            if cmdline_[0] != self.python_executable:
                cmdline_.insert(0, self.python_executable)
        return cmdline_


@attr.s(kw_only=True, slots=True)
class SaltMinion(DaemonPkgMixin, minion.SaltMinion):
    """
    Subclassed just to tweak the binary paths if needed and factory classes.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt-minion"
        minion.SaltMinion.__attrs_post_init__(self)
        DaemonPkgMixin.__attrs_post_init__(self)

    def _get_impl_class(self):
        if self.system_install and self.salt_pkg_install.system_service:
            if platform.is_windows():
                return PkgSsmSaltDaemonImpl
            if platform.is_darwin():
                return PkgLaunchdSaltDaemonImpl
            return PkgSystemdSaltDaemonImpl
        return DaemonImpl

    def write_launchd_conf(self):
        self.salt_pkg_install.write_launchd_conf("minion")

    def write_systemd_conf(self):
        self.salt_pkg_install.write_systemd_conf(
            "salt-minion", self.salt_pkg_install.binary_paths["minion"]
        )

    def salt_call_cli(self, **factory_class_kwargs):
        return super().salt_call_cli(
            factory_class=SaltCall,
            salt_pkg_install=self.salt_pkg_install,
            **factory_class_kwargs,
        )


@attr.s(kw_only=True, slots=True)
class SaltApi(DaemonPkgMixin, api.SaltApi):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt-api"
        api.SaltApi.__attrs_post_init__(self)
        DaemonPkgMixin.__attrs_post_init__(self)

    def _get_impl_class(self):
        if self.system_install and self.salt_pkg_install.system_service:
            if platform.is_windows():
                return PkgSsmSaltDaemonImpl
            if platform.is_darwin():
                return PkgLaunchdSaltDaemonImpl
            return PkgSystemdSaltDaemonImpl
        return DaemonImpl

    def write_launchd_conf(self):
        self.salt_pkg_install.write_launchd_conf("api")

    def write_systemd_conf(self):
        self.salt_pkg_install.write_systemd_conf(
            "salt-api",
            self.salt_pkg_install.binary_paths["api"],
        )


@attr.s(kw_only=True, slots=True)
class SaltCall(PkgMixin, call.SaltCall):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        call.SaltCall.__attrs_post_init__(self)
        self.script_name = "salt-call"


@attr.s(kw_only=True, slots=True)
class SaltCli(PkgMixin, salt.SaltCli):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt"
        salt.SaltCli.__attrs_post_init__(self)


@attr.s(kw_only=True, slots=True)
class SaltKey(PkgMixin, key.SaltKey):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt-key"
        key.SaltKey.__attrs_post_init__(self)


@attr.s(kw_only=True, slots=True)
class TestUser:
    """
    Add a test user
    """

    salt_call_cli = attr.ib()

    username = attr.ib(default="saltdev")
    # Must follow Windows Password Complexity requirements
    password = attr.ib(default="P@ssW0rd")
    _pw_record = attr.ib(init=False, repr=False, default=None)

    def salt_call_local(self, *args):
        ret = self.salt_call_cli.run("--local", *args)
        if ret.returncode != 0:
            log.error(ret)
        assert ret.returncode == 0
        return ret.data

    def add_user(self):
        log.debug("Adding system account %r", self.username)
        if platform.is_windows():
            self.salt_call_local("user.add", self.username, self.password)
        else:
            self.salt_call_local("user.add", self.username)
            hash_passwd = crypt.crypt(self.password, crypt.mksalt(crypt.METHOD_SHA512))
            self.salt_call_local("shadow.set_password", self.username, hash_passwd)
        assert self.username in self.salt_call_local("user.list_users")

    def remove_user(self):
        log.debug("Removing system account %r", self.username)
        if platform.is_windows():
            self.salt_call_local(
                "user.delete", self.username, "purge=True", "force=True"
            )
        else:
            self.salt_call_local("user.delete", self.username, "remove=True")

    @property
    def pw_record(self):
        if self._pw_record is None and HAS_PWD:
            self._pw_record = pwd.getpwnam(self.username)
        return self._pw_record

    @property
    def uid(self):
        if HAS_PWD:
            return self.pw_record.pw_uid
        return None

    @property
    def gid(self):
        if HAS_PWD:
            return self.pw_record.pw_gid
        return None

    @property
    def env(self):
        environ = os.environ.copy()
        environ["LOGNAME"] = environ["USER"] = self.username
        environ["HOME"] = self.pw_record.pw_dir
        return environ

    def __enter__(self):
        self.add_user()
        return self

    def __exit__(self, *_):
        self.remove_user()


@attr.s(kw_only=True, slots=True)
class ApiRequest:
    salt_api: SaltApi = attr.ib(repr=False)
    test_account: TestUser = attr.ib(repr=False)
    session: requests.Session = attr.ib(init=False, repr=False)
    api_uri: str = attr.ib(init=False)
    auth_data: Dict[str, str] = attr.ib(init=False)

    @session.default
    def _default_session(self):
        return requests.Session()

    @api_uri.default
    def _default_api_uri(self):
        return f"http://localhost:{self.salt_api.config['rest_cherrypy']['port']}"

    @auth_data.default
    def _default_auth_data(self):
        return {
            "username": self.test_account.username,
            "password": self.test_account.password,
            "eauth": "auto",
            "out": "json",
        }

    def post(self, url, data):
        post_data = dict(**self.auth_data, **data)
        resp = self.session.post(f"{self.api_uri}/run", data=post_data).json()
        minion = next(iter(resp["return"][0]))
        return resp["return"][0][minion]

    def __enter__(self):
        self.session.__enter__()
        return self

    def __exit__(self, *args):
        self.session.__exit__(*args)


@pytest.helpers.register
def remove_stale_minion_key(master, minion_id):
    key_path = os.path.join(master.config["pki_dir"], "minions", minion_id)
    if os.path.exists(key_path):
        os.unlink(key_path)
    else:
        log.debug("The minion(id=%r) key was not found at %s", minion_id, key_path)


@pytest.helpers.register
def remove_stale_master_key(master):
    keys_path = os.path.join(master.config["pki_dir"], "master")
    for key_name in ("master.pem", "master.pub"):
        key_path = os.path.join(keys_path, key_name)
        if os.path.exists(key_path):
            os.unlink(key_path)
        else:
            log.debug(
                "The master(id=%r) %s key was not found at %s",
                master.id,
                key_name,
                key_path,
            )
    key_path = os.path.join(master.config["pki_dir"], "minion", "minion_master.pub")
    if os.path.exists(key_path):
        os.unlink(key_path)
    else:
        log.debug(
            "The master(id=%r) minion_master.pub key was not found at %s",
            master.id,
            key_path,
        )
