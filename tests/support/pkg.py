import atexit
import contextlib
import logging
import os
import pathlib
import pprint
import re
import shutil
import textwrap
import time
from typing import TYPE_CHECKING, Dict, List

import attr
import distro
import packaging
import psutil
import pytest
import requests
import saltfactories.cli
from pytestshellutils.shell import DaemonImpl, Subprocess
from pytestshellutils.utils.processes import (
    ProcessResult,
    _get_cmdline,
    terminate_process,
)
from pytestskipmarkers.utils import platform
from saltfactories.bases import SystemdSaltDaemonImpl
from saltfactories.cli import call, key
from saltfactories.daemons import api, master, minion
from saltfactories.utils import cli_scripts

import salt.utils.files
from tests.conftest import CODE_DIR
from tests.support.pytest.helpers import TestAccount, download_file

ARTIFACTS_DIR = CODE_DIR / "artifacts" / "pkg"

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class SaltPkgInstall:
    pkg_system_service: bool = attr.ib(default=False)
    proc: Subprocess = attr.ib(init=False, repr=False)

    # Paths
    root: pathlib.Path = attr.ib(default=None)
    run_root: pathlib.Path = attr.ib(default=None)
    ssm_bin: pathlib.Path = attr.ib(default=None)
    bin_dir: pathlib.Path = attr.ib(default=None)
    install_dir: pathlib.Path = attr.ib(init=False)
    binary_paths: Dict[str, List[pathlib.Path]] = attr.ib(init=False)
    config_path: str = attr.ib(init=False)
    conf_dir: pathlib.Path = attr.ib()

    # Test selection flags
    upgrade: bool = attr.ib(default=False)
    downgrade: bool = attr.ib(default=False)
    classic: bool = attr.ib(default=False)

    # Installing flags
    no_install: bool = attr.ib(default=False)
    no_uninstall: bool = attr.ib(default=False)

    # Distribution/system information
    distro_id: str = attr.ib(init=False)
    distro_codename: str = attr.ib(init=False)
    distro_name: str = attr.ib(init=False)
    distro_version: str = attr.ib(init=False)

    # Version information
    prev_version: str = attr.ib()
    use_prev_version: str = attr.ib()
    artifact_version: str = attr.ib(init=False)
    version: str = attr.ib(init=False)

    # Package (and management) metadata
    pkg_mngr: str = attr.ib(init=False)
    rm_pkg: str = attr.ib(init=False)
    dbg_pkg: str = attr.ib(init=False)
    salt_pkgs: List[str] = attr.ib(init=False)
    pkgs: List[str] = attr.ib(factory=list)
    file_ext: bool = attr.ib(default=None)
    relenv: bool = attr.ib(default=True)

    @proc.default
    def _default_proc(self):
        return Subprocess()

    @distro_id.default
    def _default_distro_id(self):
        return distro.id().lower()

    @distro_codename.default
    def _default_distro_codename(self):
        return distro.codename().lower()

    @distro_name.default
    def _default_distro_name(self):
        name = distro.name()
        if name:
            if "vmware" in name.lower():
                return name.split()[1].lower()
            return name.split()[0].lower()

    @distro_version.default
    def _default_distro_version(self):
        if self.distro_name == "photon":
            return distro.version().split(".")[0]
        return distro.version().lower()

    @pkg_mngr.default
    def _default_pkg_mngr(self):
        if self.distro_id in (
            "almalinux",
            "centos",
            "redhat",
            "amzn",
            "fedora",
            "photon",
        ):
            return "yum"
        elif self.distro_id in ("ubuntu", "debian"):
            ret = self.proc.run("apt-get", "update")
            self._check_retcode(ret)
            return "apt-get"

    @rm_pkg.default
    def _default_rm_pkg(self):
        if self.distro_id in (
            "almalinux",
            "centos",
            "redhat",
            "amzn",
            "fedora",
            "photon",
        ):
            return "remove"
        elif self.distro_id in ("ubuntu", "debian"):
            return "purge"

    @dbg_pkg.default
    def _default_dbg_pkg(self):
        dbg_pkg = None
        if self.distro_id in (
            "almalinux",
            "centos",
            "redhat",
            "amzn",
            "fedora",
            "photon",
        ):
            dbg_pkg = "salt-debuginfo"
        elif self.distro_id in ("ubuntu", "debian"):
            dbg_pkg = "salt-dbg"
        return dbg_pkg

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
        if self.distro_id in (
            "almalinux",
            "centos",
            "redhat",
            "amzn",
            "fedora",
            "photon",
        ):
            salt_pkgs.append("salt")
        elif self.distro_id in ("ubuntu", "debian"):
            salt_pkgs.append("salt-common")
        if packaging.version.parse(self.version) >= packaging.version.parse("3006.3"):
            if self.dbg_pkg:
                salt_pkgs.append(self.dbg_pkg)
        return salt_pkgs

    @install_dir.default
    def _default_install_dir(self):
        if platform.is_windows():
            install_dir = pathlib.Path(
                os.getenv("ProgramFiles"), "Salt Project", "Salt"
            ).resolve()
        elif platform.is_darwin():
            install_dir = pathlib.Path("/opt", "salt")
        else:
            install_dir = pathlib.Path("/opt", "saltstack", "salt")
        return install_dir

    @config_path.default
    def _default_config_path(self):
        """
        Default location for salt configurations
        """
        if platform.is_windows():
            config_path = pathlib.Path("C://salt", "etc", "salt")
        else:
            config_path = pathlib.Path("/etc", "salt")
        return config_path

    @version.default
    def _default_version(self):
        """
        The version to be installed at the start
        """
        if not self.upgrade and not self.use_prev_version:
            version = self.artifact_version
        else:
            version = self.prev_version
            parsed = packaging.version.parse(version)
            version = f"{parsed.major}.{parsed.minor}"
        if self.distro_id in ("ubuntu", "debian"):
            self.stop_services()
        return version

    @artifact_version.default
    def _default_artifact_version(self):
        """
        The version of the local salt artifacts being tested, based on regex matching
        """
        version = ""
        artifacts = list(ARTIFACTS_DIR.glob("**/*.*"))
        for artifact in artifacts:
            version = re.search(
                r"([0-9].*)(\-[0-9].fc|\-[0-9].el|\+ds|\_all|\_any|\_amd64|\_arm64|\-[0-9].am|(\-[0-9]-[a-z]*-[a-z]*[0-9_]*.|\-[0-9]*.*)(exe|msi|pkg|rpm|deb))",
                artifact.name,
            )
            if version:
                version = version.groups()[0].replace("_", "-").replace("~", "")
                version = version.split("-")[0]
                break
        if not version:
            pytest.fail(
                f"Failed to package artifacts in '{ARTIFACTS_DIR}'. "
                f"Directory Contents:\n{pprint.pformat(artifacts)}"
            )
        return version

    def update_process_path(self):
        # The installer updates the path for the system, but that doesn't
        # make it to this python session, so we need to update that
        os.environ["PATH"] = ";".join([str(self.install_dir), os.getenv("path")])

    def __attrs_post_init__(self):
        self.relenv = packaging.version.parse(self.version) >= packaging.version.parse(
            "3006.0"
        )

        file_ext_re = "rpm|deb"
        if platform.is_darwin():
            file_ext_re = "pkg"
        if platform.is_windows():
            file_ext_re = "exe|msi"

        for f_path in ARTIFACTS_DIR.glob("**/*.*"):
            f_path = str(f_path)
            if re.search(f"salt-(.*).({file_ext_re})$", f_path, re.IGNORECASE):
                self.file_ext = os.path.splitext(f_path)[1].strip(".")
                self.pkgs.append(f_path)
                if platform.is_windows():
                    self.root = pathlib.Path(os.getenv("LocalAppData")).resolve()
                    if self.file_ext in ["exe", "msi"]:
                        self.root = self.install_dir.parent
                        self.bin_dir = self.install_dir
                        self.ssm_bin = self.install_dir / "ssm.exe"
                        self.run_root = self.bin_dir / "bin" / "salt.exe"
                        if not self.relenv and not self.classic:
                            self.ssm_bin = self.bin_dir / "bin" / "ssm.exe"
                    else:
                        log.error("Unexpected file extension: %s", self.file_ext)
                    if self.use_prev_version:
                        self.bin_dir = self.install_dir / "bin"
                        self.run_root = self.bin_dir / "salt.exe"
                        self.ssm_bin = self.bin_dir / "ssm.exe"
                        if self.file_ext == "msi" or self.relenv:
                            self.ssm_bin = self.install_dir / "ssm.exe"
                        if (
                            self.install_dir / "salt-minion.exe"
                        ).exists() and not self.relenv:
                            log.debug(
                                "Removing %s", self.install_dir / "salt-minion.exe"
                            )
                            (self.install_dir / "salt-minion.exe").unlink()

                elif platform.is_darwin():
                    self.root = pathlib.Path("/opt")
                    if self.file_ext == "pkg":
                        self.bin_dir = self.root / "salt" / "bin"
                        self.run_root = self.bin_dir / "run"
                    else:
                        log.error("Unexpected file extension: %s", self.file_ext)

        if not self.pkgs:
            pytest.fail("Could not find Salt Artifacts")

        python_bin = self.install_dir / "bin" / "python3"
        if platform.is_windows():
            python_bin = self.install_dir / "Scripts" / "python.exe"
            if self.relenv:
                self.binary_paths = {
                    "call": ["salt-call.exe"],
                    "cp": ["salt-cp.exe"],
                    "minion": ["salt-minion.exe"],
                    "pip": ["salt-pip.exe"],
                    "python": [python_bin],
                }
            elif self.classic:
                self.binary_paths = {
                    "call": [self.install_dir / "salt-call.bat"],
                    "cp": [self.install_dir / "salt-cp.bat"],
                    "minion": [self.install_dir / "salt-minion.bat"],
                    "python": [self.bin_dir / "python.exe"],
                }
                self.binary_paths["pip"] = self.binary_paths["python"] + ["-m", "pip"]
            else:
                self.binary_paths = {
                    "call": [str(self.run_root), "call"],
                    "cp": [str(self.run_root), "cp"],
                    "minion": [str(self.run_root), "minion"],
                    "pip": [str(self.run_root), "pip"],
                    "python": [str(self.run_root), "shell"],
                }

        else:
            if os.path.exists(self.install_dir / "bin" / "salt"):
                install_dir = self.install_dir / "bin"
            else:
                install_dir = self.install_dir
            if self.relenv:
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
                self.binary_paths = {
                    "salt": [shutil.which("salt")],
                    "api": [shutil.which("salt-api")],
                    "call": [shutil.which("salt-call")],
                    "cloud": [shutil.which("salt-cloud")],
                    "cp": [shutil.which("salt-cp")],
                    "key": [shutil.which("salt-key")],
                    "master": [shutil.which("salt-master")],
                    "minion": [shutil.which("salt-minion")],
                    "proxy": [shutil.which("salt-proxy")],
                    "run": [shutil.which("salt-run")],
                    "ssh": [shutil.which("salt-ssh")],
                    "syndic": [shutil.which("salt-syndic")],
                    "spm": [shutil.which("spm")],
                    "python": [str(pathlib.Path("/usr/bin/python3"))],
                }
                if self.classic:
                    if platform.is_darwin():
                        # `which` is not catching the right paths on downgrades, explicitly defining them here
                        self.binary_paths = {
                            "salt": [self.bin_dir / "salt"],
                            "api": [self.bin_dir / "salt-api"],
                            "call": [self.bin_dir / "salt-call"],
                            "cloud": [self.bin_dir / "salt-cloud"],
                            "cp": [self.bin_dir / "salt-cp"],
                            "key": [self.bin_dir / "salt-key"],
                            "master": [self.bin_dir / "salt-master"],
                            "minion": [self.bin_dir / "salt-minion"],
                            "proxy": [self.bin_dir / "salt-proxy"],
                            "run": [self.bin_dir / "salt-run"],
                            "ssh": [self.bin_dir / "salt-ssh"],
                            "syndic": [self.bin_dir / "salt-syndic"],
                            "spm": [self.bin_dir / "spm"],
                            "python": [str(self.bin_dir / "python3")],
                            "pip": [str(self.bin_dir / "pip3")],
                        }
                    else:
                        self.binary_paths["pip"] = [str(pathlib.Path("/usr/bin/pip3"))]
                        self.proc.run(*self.binary_paths["pip"], "install", "-U", "pip")
                        self.proc.run(
                            *self.binary_paths["pip"], "install", "-U", "pyopenssl"
                        )
                else:
                    self.binary_paths["python"] = [shutil.which("salt"), "shell"]
                    if platform.is_darwin():
                        self.binary_paths["pip"] = [self.run_root, "pip"]
                        self.binary_paths["spm"] = [shutil.which("salt-spm")]
                    else:
                        self.binary_paths["pip"] = [shutil.which("salt-pip")]

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

    def _install_pkgs(self, upgrade=False, downgrade=False):
        if downgrade:
            self.install_previous(downgrade=downgrade)
            return True
        pkg = self.pkgs[0]
        if platform.is_windows():
            if upgrade:
                self.root = self.install_dir.parent
                self.bin_dir = self.install_dir
                self.ssm_bin = self.install_dir / "ssm.exe"
            if pkg.endswith("exe"):
                # Install the package
                log.debug("Installing: %s", str(pkg))
                # ret = self.proc.run("start", "/wait", f"\"{str(pkg)} /start-minion=0 /S\"")
                batch_file = pathlib.Path(pkg).parent / "install_nsis.cmd"
                batch_content = f"start /wait {str(pkg)} /start-minion=0 /S"
                with salt.utils.files.fopen(batch_file, "w") as fp:
                    fp.write(batch_content)
                # Now run the batch file
                ret = self.proc.run("cmd.exe", "/c", str(batch_file))
                self._check_retcode(ret)
            elif pkg.endswith("msi"):
                # Install the package
                log.debug("Installing: %s", str(pkg))
                # Write a batch file to run the installer. It is impossible to
                # perform escaping of the START_MINION property that the MSI
                # expects unless we do it via a batch file
                batch_file = pathlib.Path(pkg).parent / "install_msi.cmd"
                batch_content = f'msiexec /qn /i "{str(pkg)}" START_MINION=""\n'
                with salt.utils.files.fopen(batch_file, "w") as fp:
                    fp.write(batch_content)
                # Now run the batch file
                ret = self.proc.run("cmd.exe", "/c", str(batch_file))
                self._check_retcode(ret)
            else:
                log.error("Invalid package: %s", pkg)
                return False

            # Remove the service installed by the installer
            log.debug("Removing installed salt-minion service")
            self.proc.run(str(self.ssm_bin), "remove", "salt-minion", "confirm")
            self.update_process_path()

        elif platform.is_darwin():
            daemons_dir = pathlib.Path("/Library", "LaunchDaemons")
            service_name = "com.saltstack.salt.minion"
            plist_file = daemons_dir / f"{service_name}.plist"
            log.debug("Installing: %s", str(pkg))
            ret = self.proc.run("installer", "-pkg", str(pkg), "-target", "/")
            self._check_retcode(ret)
            # Stop the service installed by the installer
            self.proc.run("launchctl", "disable", f"system/{service_name}")
            self.proc.run("launchctl", "bootout", "system", str(plist_file))
        elif upgrade:
            env = os.environ.copy()
            extra_args = []
            if self.distro_id in ("ubuntu", "debian"):
                env["DEBIAN_FRONTEND"] = "noninteractive"
                extra_args = [
                    "-o",
                    "DPkg::Options::=--force-confdef",
                    "-o",
                    "DPkg::Options::=--force-confold",
                ]
            log.info("Installing packages:\n%s", pprint.pformat(self.pkgs))
            args = extra_args + self.pkgs
            upgrade_cmd = "upgrade"
            if self.distro_id == "photon":
                # tdnf does not detect nightly build versions to be higher version
                # than release versions
                upgrade_cmd = "install"
            ret = self.proc.run(
                self.pkg_mngr,
                upgrade_cmd,
                "-y",
                *args,
                _timeout=120,
                env=env,
            )
        else:
            log.info("Installing packages:\n%s", pprint.pformat(self.pkgs))
            ret = self.proc.run(self.pkg_mngr, "install", "-y", *self.pkgs)
        if not platform.is_darwin() and not platform.is_windows():
            # Make sure we don't have any trailing references to old package file locations
            assert ret.returncode == 0
            assert "/saltstack/salt/run" not in ret.stdout
        log.info(ret)
        self._check_retcode(ret)

    def package_python_version(self):
        return self.proc.run(
            str(self.binary_paths["python"][0]),
            "-c",
            "import sys; print('{}.{}'.format(*sys.version_info))",
        ).stdout.strip()

    def install(self, upgrade=False, downgrade=False):
        self._install_pkgs(upgrade=upgrade, downgrade=downgrade)
        if self.distro_id in ("ubuntu", "debian"):
            self.stop_services()

    def stop_services(self):
        """
        Debian distros automatically start the services
        We want to ensure our tests start with the config
        settings we have set. This will also verify the expected
        services are up and running.
        """
        retval = True
        for service in ["salt-syndic", "salt-master", "salt-minion"]:
            check_run = self.proc.run("systemctl", "status", service)
            if check_run.returncode != 0:
                # The system was not started automatically and we
                # are expecting it to be on install
                log.debug("The service %s was not started on install.", service)
                retval = False
            else:
                stop_service = self.proc.run("systemctl", "stop", service)
                self._check_retcode(stop_service)
        return retval

    def install_previous(self, downgrade=False):
        """
        Install previous version. This is used for
        upgrade tests.
        """
        major_ver = packaging.version.parse(self.prev_version).major
        relenv = packaging.version.parse(self.prev_version) >= packaging.version.parse(
            "3006.0"
        )
        distro_name = self.distro_name
        if distro_name in ("almalinux", "centos", "fedora"):
            distro_name = "redhat"
        root_url = "salt/py3/"
        if self.classic:
            root_url = "py3/"

        if self.distro_name in [
            "almalinux",
            "redhat",
            "centos",
            "amazon",
            "fedora",
            "vmware",
            "photon",
        ]:
            # Removing EPEL repo files
            for fp in pathlib.Path("/etc", "yum.repos.d").glob("epel*"):
                fp.unlink()
            gpg_key = "SALTSTACK-GPG-KEY.pub"
            if self.distro_version == "9":
                gpg_key = "SALTSTACK-GPG-KEY2.pub"
            if relenv:
                gpg_key = "SALT-PROJECT-GPG-PUBKEY-2023.pub"

            if platform.is_aarch64():
                arch = "arm64"
                # Starting with 3006.5, we prioritize the aarch64 repo paths for rpm-based distros
                if packaging.version.parse(
                    self.prev_version
                ) >= packaging.version.parse("3006.5"):
                    arch = "aarch64"
            else:
                arch = "x86_64"
            ret = self.proc.run(
                "rpm",
                "--import",
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}/{gpg_key}",
            )
            self._check_retcode(ret)
            download_file(
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}.repo",
                f"/etc/yum.repos.d/salt-{distro_name}.repo",
            )
            if self.distro_name == "photon":
                # yum version on photon doesn't support expire-cache
                ret = self.proc.run(self.pkg_mngr, "clean", "all")
            else:
                ret = self.proc.run(self.pkg_mngr, "clean", "expire-cache")
            self._check_retcode(ret)
            cmd_action = "downgrade" if downgrade else "install"
            pkgs_to_install = self.salt_pkgs.copy()
            if self.distro_version == "8" and self.classic:
                # centosstream 8 doesn't downgrade properly using the downgrade command for some reason
                # So we explicitly install the correct version here
                list_ret = self.proc.run(
                    self.pkg_mngr, "list", "--available", "salt"
                ).stdout.split("\n")
                list_ret = [_.strip() for _ in list_ret]
                idx = list_ret.index("Available Packages")
                old_ver = list_ret[idx + 1].split()[1]
                pkgs_to_install = [f"{pkg}-{old_ver}" for pkg in pkgs_to_install]
                if self.dbg_pkg:
                    # self.dbg_pkg does not exist on classic packages
                    dbg_exists = [x for x in pkgs_to_install if self.dbg_pkg in x]
                    if dbg_exists:
                        pkgs_to_install.remove(dbg_exists[0])
                cmd_action = "install"
            ret = self.proc.run(
                self.pkg_mngr,
                cmd_action,
                *pkgs_to_install,
                "-y",
            )
            self._check_retcode(ret)

        elif distro_name in ["debian", "ubuntu"]:
            ret = self.proc.run(self.pkg_mngr, "install", "curl", "-y")
            self._check_retcode(ret)
            ret = self.proc.run(self.pkg_mngr, "install", "apt-transport-https", "-y")
            self._check_retcode(ret)
            ## only classic 3005 has arm64 support
            if relenv and platform.is_aarch64():
                arch = "arm64"
            elif platform.is_aarch64() and self.classic:
                arch = "arm64"
            else:
                arch = "amd64"
            pathlib.Path("/etc/apt/keyrings").mkdir(parents=True, exist_ok=True)
            gpg_dest = "salt-archive-keyring.gpg"
            gpg_key = gpg_dest
            if relenv:
                gpg_key = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"

            download_file(
                f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver}/{gpg_key}",
                f"/etc/apt/keyrings/{gpg_dest}",
            )
            with salt.utils.files.fopen(
                pathlib.Path("/etc", "apt", "sources.list.d", "salt.list"), "w"
            ) as fp:
                fp.write(
                    f"deb [signed-by=/etc/apt/keyrings/{gpg_dest} arch={arch}] "
                    f"https://repo.saltproject.io/{root_url}{distro_name}/{self.distro_version}/{arch}/{major_ver} {self.distro_codename} main"
                )
            self._check_retcode(ret)

            cmd = [
                self.pkg_mngr,
                "install",
                *self.salt_pkgs,
                "-y",
            ]

            if downgrade:
                pref_file = pathlib.Path("/etc", "apt", "preferences.d", "salt.pref")
                pref_file.parent.mkdir(exist_ok=True)
                pref_file.write_text(
                    textwrap.dedent(
                        """\
                Package: salt*
                Pin: origin "repo.saltproject.io"
                Pin-Priority: 1001
                """
                    ),
                    encoding="utf-8",
                )
                cmd.append("--allow-downgrades")
            env = os.environ.copy()
            env["DEBIAN_FRONTEND"] = "noninteractive"
            extra_args = [
                "-o",
                "DPkg::Options::=--force-confdef",
                "-o",
                "DPkg::Options::=--force-confold",
            ]
            ret = self.proc.run(self.pkg_mngr, "update", *extra_args, env=env)

            cmd.extend(extra_args)

            ret = self.proc.run(*cmd, env=env)
            # Pre-relenv packages down get downgraded to cleanly programmatically
            # They work manually, and the install tests after downgrades will catch problems with the install
            # Let's not check the returncode if this is the case
            if not (
                downgrade
                and packaging.version.parse(self.prev_version)
                < packaging.version.parse("3006.0")
            ):
                self._check_retcode(ret)
            if downgrade:
                pref_file.unlink()
            self.stop_services()
        elif platform.is_windows():
            self.bin_dir = self.install_dir / "bin"
            self.run_root = self.bin_dir / "salt.exe"
            self.ssm_bin = self.bin_dir / "ssm.exe"
            if self.file_ext == "msi" or relenv:
                self.ssm_bin = self.install_dir / "ssm.exe"

            if not self.classic:
                if not relenv:
                    win_pkg = (
                        f"salt-{self.prev_version}-1-windows-amd64.{self.file_ext}"
                    )
                else:
                    if self.file_ext == "msi":
                        win_pkg = (
                            f"Salt-Minion-{self.prev_version}-Py3-AMD64.{self.file_ext}"
                        )
                    elif self.file_ext == "exe":
                        win_pkg = f"Salt-Minion-{self.prev_version}-Py3-AMD64-Setup.{self.file_ext}"
                win_pkg_url = f"https://repo.saltproject.io/salt/py3/windows/{major_ver}/{win_pkg}"
            else:
                if self.file_ext == "msi":
                    win_pkg = (
                        f"Salt-Minion-{self.prev_version}-Py3-AMD64.{self.file_ext}"
                    )
                elif self.file_ext == "exe":
                    win_pkg = f"Salt-Minion-{self.prev_version}-Py3-AMD64-Setup.{self.file_ext}"
                win_pkg_url = f"https://repo.saltproject.io/windows/{win_pkg}"
            pkg_path = pathlib.Path(r"C:\TEMP", win_pkg)
            pkg_path.parent.mkdir(exist_ok=True)
            download_file(win_pkg_url, pkg_path)

            if self.file_ext == "msi":
                # Write a batch file to run the installer. It is impossible to
                # perform escaping of the START_MINION property that the MSI
                # expects unless we do it via a batch file
                batch_file = pkg_path.parent / "install_msi.cmd"
                batch_content = f'msiexec /qn /i {str(pkg_path)} START_MINION=""'
                with salt.utils.files.fopen(batch_file, "w") as fp:
                    fp.write(batch_content)
                # Now run the batch file
                ret = self.proc.run("cmd.exe", "/c", str(batch_file))
                self._check_retcode(ret)
            else:
                # ret = self.proc.run("start", "/wait", f"\"{pkg_path} /start-minion=0 /S\"")
                batch_file = pkg_path.parent / "install_nsis.cmd"
                batch_content = f"start /wait {str(pkg_path)} /start-minion=0 /S"
                with salt.utils.files.fopen(batch_file, "w") as fp:
                    fp.write(batch_content)
                # Now run the batch file
                ret = self.proc.run("cmd.exe", "/c", str(batch_file))
                self._check_retcode(ret)

            log.debug("Removing installed salt-minion service")
            ret = self.proc.run(str(self.ssm_bin), "remove", "salt-minion", "confirm")
            self._check_retcode(ret)

            if self.pkg_system_service:
                self._install_system_service()

        elif platform.is_darwin():
            if self.classic:
                mac_pkg = f"salt-{self.prev_version}-py3-x86_64.pkg"
                mac_pkg_url = f"https://repo.saltproject.io/osx/{mac_pkg}"
            else:
                if not relenv:
                    mac_pkg = f"salt-{self.prev_version}-1-macos-x86_64.pkg"
                else:
                    mac_pkg = f"salt-{self.prev_version}-py3-x86_64.pkg"
                mac_pkg_url = (
                    f"https://repo.saltproject.io/salt/py3/macos/{major_ver}/{mac_pkg}"
                )

            mac_pkg_path = f"/tmp/{mac_pkg}"
            if not os.path.exists(mac_pkg_path):
                download_file(
                    f"{mac_pkg_url}",
                    f"/tmp/{mac_pkg}",
                )

            ret = self.proc.run("installer", "-pkg", mac_pkg_path, "-target", "/")
            self._check_retcode(ret)

    def uninstall(self):
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
            # From here: https://stackoverflow.com/a/46118276/4581998
            daemons_dir = pathlib.Path("/Library", "LaunchDaemons")
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

            log.debug("Deleting the onedir directory: %s", self.root / "salt")
            shutil.rmtree(str(self.root / "salt"))
        else:
            log.debug("Un-Installing packages:\n%s", pprint.pformat(self.salt_pkgs))
            ret = self.proc.run(self.pkg_mngr, self.rm_pkg, "-y", *self.salt_pkgs)
            self._check_retcode(ret)

    def write_launchd_conf(self, service):
        service_name = f"com.saltstack.salt.{service}"
        ret = self.proc.run("launchctl", "list", service_name)
        # 113 means it couldn't find a service with that name
        if ret.returncode == 113:
            daemons_dir = pathlib.Path("/Library", "LaunchDaemons")
            plist_file = daemons_dir / f"{service_name}.plist"
            # Make sure we're using this plist file
            if plist_file.exists():
                log.warning("Removing existing plist file for service: %s", service)
                plist_file.unlink()

            log.debug("Creating plist file for service: %s", service)
            contents = f"""\
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
                        <array>"""
            for part in self.binary_paths[service]:
                contents += (
                    f"""\n                            <string>{part}</string>\n"""
                )
            contents += f"""\
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
            plist_file.write_text(textwrap.dedent(contents), encoding="utf-8")
            contents = plist_file.read_text()
            log.debug("Created '%s'. Contents:\n%s", plist_file, contents)

            # Delete the plist file upon completion
            atexit.register(plist_file.unlink)

    def write_systemd_conf(self, service, binary):
        ret = self.proc.run("systemctl", "daemon-reload")
        self._check_retcode(ret)
        ret = self.proc.run("systemctl", "status", service)
        if ret.returncode == 4:
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
            unit_path = pathlib.Path(f"/etc/systemd/system/{service}.service")
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


class PkgSystemdSaltDaemonImpl(SystemdSaltDaemonImpl):
    # pylint: disable=access-member-before-definition
    def get_service_name(self):
        if self._service_name is None:
            self._service_name = self.factory.script_name
        return self._service_name

    # pylint: enable=access-member-before-definition


@attr.s(kw_only=True)
class PkgLaunchdSaltDaemonImpl(PkgSystemdSaltDaemonImpl):

    plist_file = attr.ib()

    @plist_file.default
    def _default_plist_file(self):
        daemons_dir = pathlib.Path("/Library", "LaunchDaemons")
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
            # pylint: disable=access-member-before-definition
            if TYPE_CHECKING:
                # Make mypy happy
                assert self._terminal_result
            return self._terminal_result
            # pylint: enable=access-member-before-definition

        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        pid = self.pid
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(pid).children(recursive=True):
                # pylint: disable=access-member-before-definition
                if child not in self._children:
                    self._children.append(child)
                # pylint: enable=access-member-before-definition

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

        # pylint: disable=access-member-before-definition
        if self._terminal_stdout is not None:
            self._terminal_stdout.close()
        if self._terminal_stderr is not None:
            self._terminal_stderr.close()
        # pylint: enable=access-member-before-definition
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
            # pylint: disable=access-member-before-definition
            if TYPE_CHECKING:
                # Make mypy happy
                assert self._terminal_result
            return self._terminal_result
            # pylint: enable=access-member-before-definition

        atexit.unregister(self.terminate)
        log.info("Stopping %s", self.factory)
        pid = self.pid
        # Collect any child processes information before terminating the process
        with contextlib.suppress(psutil.NoSuchProcess):
            for child in psutil.Process(pid).children(recursive=True):
                # pylint: disable=access-member-before-definition
                if child not in self._children:
                    self._children.append(child)
                # pylint: enable=access-member-before-definition

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

        # pylint: disable=access-member-before-definition
        if self._terminal_stdout is not None:
            self._terminal_stdout.close()
        if self._terminal_stderr is not None:
            self._terminal_stderr.close()
        # pylint: enable=access-member-before-definition
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
        if platform.is_darwin() and self.salt_pkg_install.classic:
            if self.salt_pkg_install.run_root and os.path.exists(
                self.salt_pkg_install.run_root
            ):
                return str(self.salt_pkg_install.run_root)
            elif os.path.exists(self.salt_pkg_install.bin_dir / self.script_name):
                return str(self.salt_pkg_install.bin_dir / self.script_name)
            else:
                return str(self.salt_pkg_install.install_dir / self.script_name)
        return super().get_script_path()

    def cmdline(self, *args, **kwargs):
        _cmdline = super().cmdline(*args, **kwargs)
        if _cmdline[0] == self.python_executable:
            _cmdline.pop(0)
        return _cmdline


@attr.s(kw_only=True)
class DaemonPkgMixin(PkgMixin):
    def __attrs_post_init__(self):
        if not platform.is_windows() and self.salt_pkg_install.pkg_system_service:
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
        if self.system_service and self.salt_pkg_install.pkg_system_service:
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

    def salt_key_cli(self, factory_class=None, **factory_class_kwargs):
        if not factory_class:
            factory_class = SaltKey
        factory_class_kwargs["salt_pkg_install"] = self.salt_pkg_install
        return super().salt_key_cli(
            factory_class=factory_class,
            **factory_class_kwargs,
        )

    def salt_cli(self, factory_class=None, **factory_class_kwargs):
        if not factory_class:
            factory_class = SaltCli
        factory_class_kwargs["salt_pkg_install"] = self.salt_pkg_install
        return super().salt_cli(
            factory_class=factory_class,
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
        if self.system_service and self.salt_pkg_install.pkg_system_service:
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

    def salt_call_cli(self, factory_class=None, **factory_class_kwargs):
        if not factory_class:
            factory_class = SaltCall
        factory_class_kwargs["salt_pkg_install"] = self.salt_pkg_install
        return super().salt_call_cli(
            factory_class=factory_class,
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
        if self.system_service and self.salt_pkg_install.pkg_system_service:
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
class SaltCli(PkgMixin, saltfactories.cli.salt.SaltCli):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt"
        saltfactories.cli.salt.SaltCli.__attrs_post_init__(self)


@attr.s(kw_only=True, slots=True)
class SaltKey(PkgMixin, key.SaltKey):
    """
    Subclassed just to tweak the binary paths if needed.
    """

    def __attrs_post_init__(self):
        self.script_name = "salt-key"
        key.SaltKey.__attrs_post_init__(self)


@attr.s(kw_only=True, slots=True)
class ApiRequest:
    port: int = attr.ib(repr=False)
    account: TestAccount = attr.ib(repr=False)
    session: requests.Session = attr.ib(init=False, repr=False)
    api_uri: str = attr.ib(init=False)
    auth_data: Dict[str, str] = attr.ib(init=False)

    @session.default
    def _default_session(self):
        return requests.Session()

    @api_uri.default
    def _default_api_uri(self):
        return f"http://localhost:{self.port}"

    @auth_data.default
    def _default_auth_data(self):
        return {
            "username": self.account.username,
            "password": self.account.password,
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
