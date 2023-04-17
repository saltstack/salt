"""
Test Salt Pkg Downloads
"""
import logging
import os
import pathlib
import shutil

import packaging
import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


def get_salt_test_commands():

    salt_release = get_salt_release()
    if platform.is_windows():
        if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
            salt_test_commands = [
                "salt-call.exe --local test.versions",
                "salt-call.exe --local grains.items",
                "salt-minion.exe --version",
            ]
        else:
            salt_test_commands = [
                "salt-call.bat --local test.versions",
                "salt-call.bat --local grains.items",
                "salt.bat --version",
                "salt-master.bat --version",
                "salt-minion.bat --version",
                "salt-ssh.bat --version",
                "salt-syndic.bat --version",
                "salt-api.bat --version",
                "salt-cloud.bat --version",
            ]
    else:
        salt_test_commands = [
            "salt-call --local test.versions",
            "salt-call --local grains.items",
            "salt --version",
            "salt-master --version",
            "salt-minion --version",
            "salt-ssh --version",
            "salt-syndic --version",
            "salt-api --version",
            "salt-cloud --version",
        ]
    return salt_test_commands


@pytest.fixture(scope="module")
def root_url(salt_release):
    if os.environ.get("SALT_REPO_TYPE", "release") == "staging":
        repo_domain = os.environ.get(
            "SALT_REPO_DOMAIN_STAGING", "staging.repo.saltproject.io"
        )
    else:
        repo_domain = os.environ.get("SALT_REPO_DOMAIN_RELEASE", "repo.saltproject.io")
    if "rc" in salt_release:
        salt_path = "salt_rc/salt"
    else:
        salt_path = "salt"
    salt_repo_user = os.environ.get("SALT_REPO_USER")
    if salt_repo_user:
        log.info(
            "SALT_REPO_USER: %s",
            salt_repo_user[0] + "*" * (len(salt_repo_user) - 2) + salt_repo_user[-1],
        )
    salt_repo_pass = os.environ.get("SALT_REPO_PASS")
    if salt_repo_pass:
        log.info(
            "SALT_REPO_PASS: %s",
            salt_repo_pass[0] + "*" * (len(salt_repo_pass) - 2) + salt_repo_pass[-1],
        )
    if salt_repo_user and salt_repo_pass:
        repo_domain = f"{salt_repo_user}:{salt_repo_pass}@{repo_domain}"
    _root_url = f"https://{repo_domain}/{salt_path}/py3"
    log.info("Repository Root URL: %s", _root_url)
    return _root_url


def get_salt_release():
    salt_release = os.environ.get("SALT_RELEASE")
    pkg_test_type = os.environ.get("PKG_TEST_TYPE", "install")
    if salt_release is None:
        if pkg_test_type == "download-pkgs":
            log.warning(
                "Setting salt release to 3006.0rc2 which is probably not what you want."
            )
        salt_release = "3006.0rc2"
    if pkg_test_type == "download-pkgs":
        if packaging.version.parse(salt_release) < packaging.version.parse("3006.0rc1"):
            log.warning(f"The salt release being tested, {salt_release!r} looks off.")
    return salt_release


@pytest.fixture(scope="module")
def gpg_key_name(salt_release):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        return "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    return "salt-archive-keyring.gpg"


@pytest.fixture(scope="module")
def salt_release():
    yield get_salt_release()


@pytest.fixture(scope="module")
def setup_system(tmp_path_factory, grains, shell, root_url, salt_release, gpg_key_name):
    downloads_path = tmp_path_factory.mktemp("downloads")
    try:
        if grains["os_family"] == "Windows":
            setup_windows(
                shell,
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
            )
        elif grains["os_family"] == "MacOS":
            setup_macos(
                shell,
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
            )
        elif grains["os"] == "Amazon":
            setup_redhat_family(
                shell,
                os_name=grains["os"].lower(),
                os_version=grains["osmajorrelease"],
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                gpg_key_name=gpg_key_name,
            )
        elif grains["os"] == "Fedora":
            setup_redhat_family(
                shell,
                os_name=grains["os"].lower(),
                os_version=grains["osmajorrelease"],
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                gpg_key_name=gpg_key_name,
            )
        elif grains["os"] == "VMware Photon OS":
            setup_redhat_family(
                shell,
                os_name="photon",
                os_version=grains["osmajorrelease"],
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                gpg_key_name=gpg_key_name,
            )
        elif grains["os_family"] == "RedHat":
            setup_redhat_family(
                shell,
                os_name="redhat",
                os_version=grains["osmajorrelease"],
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                gpg_key_name=gpg_key_name,
            )
        elif grains["os_family"] == "Debian":
            setup_debian_family(
                shell,
                os_name=grains["os"].lower(),
                os_version=grains["osrelease"],
                os_codename=grains["oscodename"],
                root_url=root_url,
                salt_release=salt_release,
                downloads_path=downloads_path,
                gpg_key_name=gpg_key_name,
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
    gpg_key_name,
):
    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    repo_url_base = f"{root_url}/{os_name}/{os_version}/{arch}/minor/{salt_release}"
    gpg_file_url = f"{root_url}/{os_name}/{os_version}/{arch}/{gpg_key_name}"
    try:
        pytest.helpers.download_file(gpg_file_url, downloads_path / gpg_key_name)
    except Exception as exc:
        pytest.fail(f"Failed to download {gpg_file_url}: {exc}")

    ret = shell.run("rpm", "--import", str(downloads_path / gpg_key_name), check=False)
    if ret.returncode != 0:
        pytest.fail("Failed to import gpg key")

    repo_file = pytest.helpers.download_file(
        f"{repo_url_base}.repo", downloads_path / f"salt-{os_name}.repo"
    )

    commands = [
        ("mv", str(repo_file), "/etc/yum.repos.d/salt.repo"),
        ("yum", "clean", "all" if os_name == "photon" else "expire-cache"),
        (
            "yum",
            "install",
            "-y",
            "salt-master",
            "salt-minion",
            "salt-ssh",
            "salt-syndic",
            "salt-cloud",
            "salt-api",
        ),
    ]

    # For some reason, the centosstream9 container doesn't have dmesg installed
    if os_version == 9 and os_name == "redhat":
        commands.insert(2, ("yum", "install", "-y", "util-linux"))

    for cmd in commands:
        ret = shell.run(*cmd, check=False)
        if ret.returncode != 0:
            pytest.fail(f"Failed to run '{' '.join(cmd)!r}':\n{ret}")


def setup_debian_family(
    shell,
    os_name,
    os_version,
    os_codename,
    root_url,
    salt_release,
    downloads_path,
    gpg_key_name,
):
    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "x86_64":
        arch = "amd64"

    ret = shell.run("apt-get", "update", "-y", check=False)
    if ret.returncode != 0:
        pytest.fail(str(ret))

    repo_url_base = f"{root_url}/{os_name}/{os_version}/{arch}/minor/{salt_release}"
    gpg_file_url = f"{root_url}/{os_name}/{os_version}/{arch}/{gpg_key_name}"
    try:
        pytest.helpers.download_file(gpg_file_url, downloads_path / gpg_key_name)
    except Exception as exc:
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
        ),
    ]
    for cmd in commands:
        ret = shell.run(*cmd)
        if ret.returncode != 0:
            pytest.fail(str(ret))


def setup_macos(shell, root_url, salt_release, downloads_path):

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        mac_pkg = f"salt-{salt_release}-py3-{arch}.pkg"
        mac_pkg_url = f"{root_url}/macos/minor/{salt_release}/{mac_pkg}"
    else:
        mac_pkg_url = f"{root_url}/macos/{salt_release}/{mac_pkg}"
        mac_pkg = f"salt-{salt_release}-macos-{arch}.pkg"

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

    yield


def setup_windows(shell, root_url, salt_release, downloads_path):

    root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")

    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    install_type = os.environ.get("INSTALL_TYPE") or "msi"
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        if install_type.lower() == "nsis":
            if arch.lower() != "x86":
                arch = arch.upper()
            win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}-Setup.exe"
        else:
            if arch.lower() != "x86":
                arch = arch.upper()
            win_pkg = f"Salt-Minion-{salt_release}-Py3-{arch}.msi"
        win_pkg_url = f"{root_url}/windows/minor/{salt_release}/{win_pkg}"
        ssm_bin = root_dir / "ssm.exe"
    else:
        win_pkg = f"salt-{salt_release}-windows-{arch}.exe"
        win_pkg_url = f"{root_url}/windows/{salt_release}/{win_pkg}"
        ssm_bin = root_dir / "bin" / "ssm_bin"

    pkg_path = downloads_path / win_pkg

    pytest.helpers.download_file(win_pkg_url, pkg_path)
    if install_type.lower() == "nsis":
        ret = shell.run(str(pkg_path), "/start-minion=0", "/S", check=False)
    else:
        ret = shell.run("msiexec", "/qn", "/i", str(pkg_path), 'START_MINION=""')
    assert ret.returncode == 0, ret

    log.debug("Removing installed salt-minion service")
    ret = shell.run(
        "cmd", "/c", str(ssm_bin), "remove", "salt-minion", "confirm", check=False
    )
    assert ret.returncode == 0, ret


@pytest.mark.usefixtures("setup_system")
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download(shell, grains, salt_test_command):
    """
    Test downloading of Salt packages and running various commands.
    """
    _cmd = salt_test_command.split()
    if grains["os_family"] == "Windows":
        root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")
        _cmd[0] = str(root_dir / _cmd[0])
    ret = shell.run(*_cmd, check=False)
    assert ret.returncode == 0, ret
