"""
Test Salt Pkg Downloads
"""

import contextlib
import logging
import os
import pathlib
import shutil
import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


def get_salt_test_commands():
    salt_release = get_salt_release()
    if platform.is_windows():
        if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
            salt_test_commands = [
                ["salt-call.exe", "--local", "test.versions"],
                ["salt-call.exe", "--local", "grains.items"],
                ["salt-minion.exe", "--version"],
            ]
        else:
            salt_test_commands = [
                ["salt-call.bat", "--local", "test.versions"],
                ["salt-call.bat", "--local", "grains.items"],
                ["salt.bat", "--version"],
                ["salt-master.bat", "--version"],
                ["salt-minion.bat", "--version"],
                ["salt-ssh.bat", "--version"],
                ["salt-syndic.bat", "--version"],
                ["salt-api.bat", "--version"],
                ["salt-cloud.bat", "--version"],
            ]
    else:
        salt_test_commands = [
            ["salt-call", "--local", "test.versions"],
            ["salt-call", "--local", "grains.items"],
            ["salt", "--version"],
            ["salt-master", "--version"],
            ["salt-minion", "--version"],
            ["salt-ssh", "--version"],
            ["salt-syndic", "--version"],
            ["salt-api", "--version"],
            ["salt-cloud", "--version"],
        ]
    return salt_test_commands


@pytest.fixture(scope="module")
def root_url(salt_release):
    default_url = "https://packages.broadcom.com/artifactory"
    repo_domain = os.environ.get("SALT_REPO_DOMAIN_RELEASE", default_url)
    log.info("Repository Root URL: %s", repo_domain)
    return repo_domain


@pytest.fixture(scope="module")
def package_type():
    return os.environ.get("DOWNLOAD_TEST_PACKAGE_TYPE")


def get_salt_release():
    salt_release = os.environ.get("SALT_RELEASE")
    pkg_test_type = os.environ.get("PKG_TEST_TYPE", "install")
    if salt_release is None:
        if pkg_test_type == "download-pkgs":
            log.warning(
                "Setting salt release to 3006.0 which is probably not what you want."
            )
        salt_release = "3006.0"
    if pkg_test_type == "download-pkgs":
        if packaging.version.parse(salt_release) < packaging.version.parse("3006.0"):
            log.warning("The salt release being tested, %r looks off.", salt_release)
    return salt_release


@pytest.fixture(scope="module")
def salt_release():
    yield get_salt_release()


@pytest.fixture(scope="module")
def onedir_install_path(tmp_path_factory):
    install_path = tmp_path_factory.mktemp("onedir_install")
    yield install_path
    shutil.rmtree(install_path, ignore_errors=True)


@pytest.fixture(scope="module")
def _setup_system(
    grains,
    shell,
    root_url,
    salt_release,
    package_type,
    tmp_path_factory,
    onedir_install_path,
):
    downloads_path = tmp_path_factory.mktemp("downloads")
    try:
        # Windows is a special case, because sometimes we need to uninstall the packages
        if grains["os_family"] == "Windows":
            with setup_windows(
                shell,
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                package_type=package_type,
                onedir_install_path=onedir_install_path,
            ):
                yield
        else:
            if grains["os_family"] == "MacOS":
                setup_macos(
                    shell,
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                    package_type=package_type,
                    onedir_install_path=onedir_install_path,
                )
            elif grains["os"] == "Amazon":
                setup_redhat_family(
                    shell,
                    os_name=grains["os"].lower(),
                    os_version=grains["osmajorrelease"],
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                )
            elif grains["os"] == "Fedora":
                setup_redhat_family(
                    shell,
                    os_name=grains["os"].lower(),
                    os_version=grains["osmajorrelease"],
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                )
            elif grains["os"] == "VMware Photon OS":
                setup_redhat_family(
                    shell,
                    os_name="photon",
                    os_version=grains["osmajorrelease"],
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                )
            elif grains["os_family"] == "RedHat":
                setup_redhat_family(
                    shell,
                    os_name="redhat",
                    os_version=grains["osmajorrelease"],
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                )
            elif grains["os_family"] == "Debian":
                setup_debian_family(
                    shell,
                    os_codename=grains["oscodename"],
                    root_url=root_url,
                    salt_release=salt_release,
                    downloads_path=downloads_path,
                    package_type=package_type,
                    onedir_install_path=onedir_install_path,
                )
            else:
                pytest.fail("Don't know how to handle %s", grains["osfinger"])
            yield
    finally:
        shutil.rmtree(downloads_path, ignore_errors=True)


def setup_redhat_family(
    shell,
    os_name,
    os_version,
    root_url,
    salt_release,
    downloads_path,
):
    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"

    if os_name == "photon":
        os_version = f"{os_version}.0"

    repo_url_base = f"{root_url}/saltproject-rpm"

    # Download the salt.repo
    # It contains the gpg key url so we don't need to download it here
    salt_repo_url = "https://github.com/saltstack/salt-install-guide/releases/latest/download/salt.repo"
    repo_file = pytest.helpers.download_file(
        salt_repo_url, downloads_path / "salt.repo"
    )

    commands = [
        ("mv", str(repo_file), "/etc/yum.repos.d/salt.repo"),
        ("yum", "clean", "all" if os_name == "photon" else "expire-cache"),
        (
            "yum",
            "install",
            "-y",
            f"salt-master-{salt_release}",
            f"salt-minion-{salt_release}",
            f"salt-ssh-{salt_release}",
            f"salt-syndic-{salt_release}",
            f"salt-cloud-{salt_release}",
            f"salt-api-{salt_release}",
            f"salt-debuginfo-{salt_release}",
        ),
    ]

    for cmd in commands:
        ret = shell.run(*cmd, check=False)
        if ret.returncode != 0:
            pytest.fail(f"Failed to run '{' '.join(cmd)!r}':\n{ret}")


def setup_debian_family(
    shell,
    os_codename,
    root_url,
    salt_release,
    downloads_path,
    package_type,
    onedir_install_path,
):
    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    ret = shell.run("apt-get", "update", "-y", check=False)
    if ret.returncode != 0:
        pytest.fail(str(ret))

    if package_type == "package":
        if arch == "aarch64":
            arch = "arm64"
        elif arch == "x86_64":
            arch = "amd64"

        repo_url_base = f"{root_url}/saltproject-deb/"
        gpg_file_url = "https://packages.broadcom.com/artifactory/api/security/keypair/SaltProjectKey/public"
        gpg_key_name = "SALT-PROJECT-GPG-PUBKEY-2023.pub"

        try:
            pytest.helpers.download_file(gpg_file_url, downloads_path / gpg_key_name)
        except Exception as exc:  # pylint: disable=broad-except
            pytest.fail(f"Failed to download {gpg_file_url}: {exc}")

        salt_sources_path = downloads_path / "salt.list"
        salt_sources_path.write_text(
            f"deb [signed-by=/usr/share/keyrings/{gpg_key_name} arch={arch}] {repo_url_base} {os_codename} main\n"
        )
        commands = [
            (
                "mv",
                str(downloads_path / gpg_key_name),
                f"/usr/share/keyrings/{gpg_key_name}",
            ),
            (
                "mv",
                str(salt_sources_path),
                "/etc/apt/sources.list.d/salt.list",
            ),
            ("apt-get", "install", "-y", "ca-certificates"),
            ("update-ca-certificates",),
            ("apt-get", "update"),
            (
                "apt-get",
                "install",
                "-y",
                "salt-master",
                "salt-minion",
                "salt-ssh",
                "salt-syndic",
                "salt-cloud",
                "salt-api",
                "salt-dbg",
            ),
        ]
        for cmd in commands:
            ret = shell.run(*cmd)
            if ret.returncode != 0:
                pytest.fail(str(ret))
    else:
        # We are testing the onedir download
        onedir_name = f"salt-{salt_release}-onedir-linux-{arch}.tar.xz"
        onedir_url = (
            f"{root_url}/saltproject-generic/onedir/{salt_release}/{onedir_name}"
        )
        onedir_location = downloads_path / onedir_name
        onedir_extracted = onedir_install_path

        try:
            pytest.helpers.download_file(onedir_url, onedir_location)
        except Exception as exc:  # pylint: disable=broad-except
            pytest.fail(f"Failed to download {onedir_url}: {exc}")

        shell.run("tar", "xvf", str(onedir_location), "-C", str(onedir_extracted))


def setup_macos(
    shell,
    root_url,
    salt_release,
    downloads_path,
    package_type,
    onedir_install_path,
):
    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if package_type == "package":
        mac_pkg = f"salt-{salt_release}-py3-{arch}.pkg"
        mac_pkg_url = f"{root_url}/saltproject-generic/macos/{salt_release}/{mac_pkg}"

        mac_pkg_path = downloads_path / mac_pkg
        pytest.helpers.download_file(mac_pkg_url, mac_pkg_path)

        ret = shell.run(
            "installer",
            "-pkg",
            str(mac_pkg_path),
            "-target",
            "/",
            check=False,
        )
        assert ret.returncode == 0, ret
    else:
        # We are testing the onedir download
        onedir_name = f"salt-{salt_release}-onedir-macos-{arch}.tar.xz"
        onedir_url = f"{root_url}/onedir/{salt_release}/{onedir_name}"
        onedir_location = downloads_path / onedir_name
        onedir_extracted = onedir_install_path

        try:
            pytest.helpers.download_file(onedir_url, onedir_location)
        except Exception as exc:  # pylint: disable=broad-except
            pytest.fail(f"Failed to download {onedir_url}: {exc}")

        shell.run("tar", "xvf", str(onedir_location), "-C", str(onedir_extracted))


@contextlib.contextmanager
def setup_windows(
    shell,
    root_url,
    salt_release,
    downloads_path,
    package_type,
    onedir_install_path,
    timeout=300,
):
    try:
        arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
        if package_type != "onedir":
            root_dir = pathlib.Path(os.getenv("ProgramFiles"), "Salt Project", "Salt")

            if package_type.lower() == "nsis":
                if arch.lower() != "x86":
                    arch = arch.upper()
                win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}-Setup.exe"
            else:
                if arch.lower() != "x86":
                    arch = arch.upper()
                win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}.msi"
            win_pkg_url = (
                f"{root_url}/saltproject-generic/windows/{salt_release}/{win_pkg}"
            )
            ssm_bin = root_dir / "ssm.exe"

            pkg_path = downloads_path / win_pkg

            pytest.helpers.download_file(win_pkg_url, pkg_path)
            if package_type.lower() == "nsis":
                # We need to make sure there are no installer/uninstaller
                # processes running. Uninst.exe launches a 2nd binary
                # (Un.exe or Un_*.exe) Let's get the name of the process
                processes = [
                    win_pkg,
                    "uninst.exe",
                    "Un.exe",
                    "Un_A.exe",
                    "Un_B.exe",
                    "Un_C.exe",
                    "Un_D.exe",
                    "Un_D.exe",
                    "Un_F.exe",
                    "Un_G.exe",
                ]
                proc_name = ""
                for proc in processes:
                    try:
                        if proc in (p.name() for p in psutil.process_iter()):
                            proc_name = proc
                    except psutil.NoSuchProcess:
                        continue

                # We need to give the process time to exit. We'll timeout after
                # 5 minutes or whatever timeout is set to
                if proc_name:
                    elapsed_time = 0
                    while elapsed_time < timeout:
                        try:
                            if proc_name not in (
                                p.name() for p in psutil.process_iter()
                            ):
                                break
                        except psutil.NoSuchProcess:
                            continue
                        elapsed_time += 0.1
                        time.sleep(0.1)

                # Only run setup when we're sure no other installations are running
                ret = shell.run(str(pkg_path), "/start-minion=0", "/S", check=False)
            else:
                ret = shell.run(
                    "msiexec", "/qn", "/i", str(pkg_path), 'START_MINION=""'
                )
            assert ret.returncode == 0, ret

            log.debug("Removing installed salt-minion service")
            ret = shell.run(
                "cmd",
                "/c",
                str(ssm_bin),
                "remove",
                "salt-minion",
                "confirm",
                check=False,
            )
            assert ret.returncode == 0, ret
        else:
            # We are testing the onedir download
            onedir_name = f"salt-{salt_release}-onedir-windows-{arch}.zip"
            onedir_url = f"{root_url}/onedir/{salt_release}/{onedir_name}"
            onedir_location = downloads_path / onedir_name
            onedir_extracted = onedir_install_path

            try:
                pytest.helpers.download_file(onedir_url, onedir_location)
            except Exception as exc:  # pylint: disable=broad-except
                pytest.fail(f"Failed to download {onedir_url}: {exc}")

            shell.run("unzip", str(onedir_location), "-d", str(onedir_extracted))
        yield
    finally:
        # We need to uninstall the MSI packages, otherwise they will not install correctly
        if package_type.lower() == "msi":
            ret = shell.run("msiexec", "/qn", "/x", str(pkg_path))
            assert ret.returncode == 0, ret


@pytest.fixture(scope="module")
def install_dir(_setup_system, package_type, onedir_install_path):
    if package_type != "onedir":
        if platform.is_windows():
            return pathlib.Path(
                os.getenv("ProgramFiles"), "Salt Project", "Salt"
            ).resolve()
        if platform.is_darwin():
            return pathlib.Path("/opt", "salt")
        return pathlib.Path("/opt", "saltstack", "salt")
    else:
        # We are testing the onedir
        return onedir_install_path / "salt"


@pytest.fixture(scope="module")
def salt_test_command(request, install_dir):
    command = request.param
    command[0] = str(install_dir / command[0])
    return command


@pytest.mark.skip_on_windows(reason="This is flaky on Windows")
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands(), indirect=True)
def test_download(shell, salt_test_command):
    """
    Test downloading of Salt packages and running various commands.
    """
    ret = shell.run(*salt_test_command, check=False)
    assert ret.returncode == 0, ret
