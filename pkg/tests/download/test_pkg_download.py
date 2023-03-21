"""
Test Salt Pkg Downloads
"""
import logging
import os
import pathlib
import re
import shutil

import attr
import packaging
import pytest
from pytestskipmarkers.utils import platform
from saltfactories.utils import random_string

log = logging.getLogger(__name__)


@attr.s(kw_only=True, slots=True)
class PkgImage:
    name = attr.ib()
    os_type = attr.ib()
    os_version = attr.ib()
    os_codename = attr.ib(default=None)
    container_id = attr.ib()
    container = attr.ib(default=None)

    def __str__(self):
        return f"{self.container_id}"


def get_test_versions():
    test_versions = []

    containers = [
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/amazon-linux:2",
            "os_type": "amazon",
            "os_version": 2,
            "container_id": "amazon_2",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos:7",
            "os_type": "redhat",
            "os_version": 7,
            "container_id": "centos_7",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos-stream:8",
            "os_type": "redhat",
            "os_version": 8,
            "container_id": "centosstream_8",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/centos-stream:9",
            "os_type": "redhat",
            "os_version": 9,
            "container_id": "centosstream_9",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:36",
            "os_type": "fedora",
            "os_version": 36,
            "container_id": "fedora_36",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:37",
            "os_type": "fedora",
            "os_version": 37,
            "container_id": "fedora_37",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/fedora:38",
            "os_type": "fedora",
            "os_version": 38,
            "container_id": "fedora_38",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/debian:10",
            "os_type": "debian",
            "os_version": 10,
            "os_codename": "buster",
            "container_id": "debian_10",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/debian:11",
            "os_type": "debian",
            "os_version": 11,
            "os_codename": "bullseye",
            "container_id": "debian_11",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/ubuntu:20.04",
            "os_type": "ubuntu",
            "os_version": 20.04,
            "os_codename": "focal",
            "container_id": "ubuntu_20_04",
        },
        {
            "image": "ghcr.io/saltstack/salt-ci-containers/ubuntu:22.04",
            "os_type": "ubuntu",
            "os_version": 22.04,
            "os_codename": "jammy",
            "container_id": "ubuntu_22_04",
        },
    ]
    for container in containers:
        test_versions.append(
            PkgImage(
                name=container["image"],
                os_type=container["os_type"],
                os_version=container["os_version"],
                os_codename=container.get("os_codename", ""),
                container_id=container["container_id"],
            )
        )

    return test_versions


def get_container_type_id(value):
    return f"{value}"


@pytest.fixture(scope="module", params=get_test_versions(), ids=get_container_type_id)
def download_test_image(request):
    return request.param


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
def pkg_container(
    salt_factories, download_test_image, root_url, salt_release, tmp_path_factory
):
    downloads_path = tmp_path_factory.mktemp("downloads")
    container = salt_factories.get_container(
        random_string(f"{download_test_image.container_id}_"),
        download_test_image.name,
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs=dict(
            volumes={
                str(downloads_path): {"bind": "/downloads", "mode": "z"},
            }
        ),
    )
    try:
        after_start_func = globals()[f"setup_{download_test_image.os_type}"]
    except KeyError:
        raise pytest.skip.Exception(
            f"Unable to handle {pkg_container.os_type}. Skipping.",
            _use_item_location=True,
        )
    container.after_start(
        after_start_func,
        container,
        download_test_image.os_version,
        download_test_image.os_codename,
        root_url,
        salt_release,
        downloads_path,
    )
    container.before_terminate(shutil.rmtree, str(downloads_path), ignore_errors=True)

    with container.started():
        download_test_image.container = container
        yield download_test_image


@pytest.fixture(scope="module")
def root_url(salt_release):
    repo_domain = os.environ.get("SALT_REPO_DOMAIN", "repo.saltproject.io")
    if "rc" in salt_release:
        salt_path = "salt_rc/salt"
    else:
        salt_path = "salt"
    salt_repo_user = os.environ.get("SALT_REPO_USER")
    if salt_repo_user:
        log.warning(
            "SALT_REPO_USER: %s",
            salt_repo_user[0] + "*" * (len(salt_repo_user) - 2) + salt_repo_user[-1],
        )
    salt_repo_pass = os.environ.get("SALT_REPO_PASS")
    if salt_repo_pass:
        log.warning(
            "SALT_REPO_PASS: %s",
            salt_repo_pass[0] + "*" * (len(salt_repo_pass) - 2) + salt_repo_pass[-1],
        )
    if salt_repo_user and salt_repo_pass:
        repo_domain = f"{salt_repo_user}:{salt_repo_pass}@{repo_domain}"
    _root_url = f"https://{repo_domain}/{salt_path}/py3"
    log.info("Repository Root URL: %s", _root_url)
    return _root_url


def get_salt_release():
    if platform.is_darwin() or platform.is_windows():
        _DEFAULT_RELEASE = "3005-1"
    else:
        _DEFAULT_RELEASE = "3005.1"
    return os.environ.get("SALT_RELEASE", _DEFAULT_RELEASE)


@pytest.fixture(scope="module")
def salt_release():
    yield get_salt_release()


def setup_redhat_family(
    container, os_version, os_codename, root_url, salt_release, downloads_path, os_name
):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.pub"
    else:
        gpg_file = "salt-archive-keyring.gpg"

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    repo_url_base = f"{root_url}/{os_name}/{os_version}/{arch}/minor/{salt_release}"
    gpg_file_url = f"{repo_url_base}/{gpg_file}"
    try:
        pytest.helpers.download_file(gpg_file_url, downloads_path / gpg_file)
    except Exception as exc:
        pytest.fail(f"Failed to download {gpg_file_url}: {exc}")

    ret = container.run("rpm", "--import", f"/downloads/{gpg_file}")
    if ret.returncode != 0:
        pytest.fail("Failed to import gpg key")

    repo_file = pytest.helpers.download_file(
        f"{repo_url_base}.repo", downloads_path / f"salt-{os_name}.repo"
    )
    repo_file_contents = repo_file.read_text()
    log.info("Repo file contents:\n%s", repo_file_contents)
    if "baseurl=" in repo_file_contents:
        repo_file_contents = re.sub(
            "baseurl=(.*)\n",
            f"baseurl={repo_url_base}\n",
            repo_file_contents,
            flags=re.MULTILINE,
        )
    else:
        repo_file_contents += f"\nbaseurl={repo_url_base}\n"
    if "gpgkey=" in repo_file_contents:
        repo_file_contents = re.sub(
            "gpgkey=(.*)\n",
            f"gpgkey={gpg_file_url}\n",
            repo_file_contents,
            flags=re.MULTILINE,
        )
    else:
        repo_file_contents += f"\ngpgkey={gpg_file_url}\n"
    log.info("Repo file contents after replacements:\n%s", repo_file_contents)
    repo_file.write_text(repo_file_contents)

    commands = [
        ("mv", f"/downloads/{repo_file.name}", f"/etc/yum.repos.d/salt-{os_name}.repo"),
        ("yum", "clean", "expire-cache"),
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
    for cmd in commands:
        ret = container.run(*cmd)
        if ret.returncode != 0:
            pytest.fail(f"Failed to run: {' '.join(cmd)!r}")


def setup_amazon(
    container, os_version, os_codename, root_url, salt_release, downloads_path
):
    setup_redhat_family(
        container,
        os_version,
        os_codename,
        root_url,
        salt_release,
        downloads_path,
        "amazon",
    )


def setup_redhat(
    container, os_version, os_codename, root_url, salt_release, downloads_path
):
    setup_redhat_family(
        container,
        os_version,
        os_codename,
        root_url,
        salt_release,
        downloads_path,
        "redhat",
    )


def setup_fedora(
    container, os_version, os_codename, root_url, salt_release, downloads_path
):
    setup_redhat_family(
        container,
        os_version,
        os_codename,
        root_url,
        salt_release,
        downloads_path,
        "fedora",
    )


def setup_debian_family(
    container, os_version, os_codename, root_url, salt_release, downloads_path, os_name
):
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        gpg_file = "SALT-PROJECT-GPG-PUBKEY-2023.gpg"
    else:
        gpg_file = "salt-archive-keyring.gpg"

    arch = os.environ.get("SALT_REPO_ARCH") or "amd64"
    if arch == "aarch64":
        arch = "arm64"
    elif arch == "x86_64":
        arch = "amd64"

    ret = container.run("apt-get", "update", "-y")
    if ret.returncode != 0:
        pytest.fail(f"Failed to run: 'apt-get update -y'")

    repo_url_base = f"{root_url}/{os_name}/{os_version}/{arch}/minor/{salt_release}"
    gpg_file_url = f"{repo_url_base}/{gpg_file}"
    try:
        pytest.helpers.download_file(gpg_file_url, downloads_path / gpg_file)
    except Exception as exc:
        pytest.fail(f"Failed to download {gpg_file_url}: {exc}")

    salt_sources_path = downloads_path / "salt.list"
    salt_sources_path.write_text(
        f"deb [signed-by=/usr/share/keyrings/{gpg_file} arch={arch}] {repo_url_base} {os_codename} main\n"
    )
    commands = [
        ("mv", f"/downloads/{gpg_file}", f"/usr/share/keyrings/{gpg_file}"),
        (
            "mv",
            f"/downloads/{salt_sources_path.name}",
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
        ret = container.run(*cmd)
        if ret.returncode != 0:
            pytest.fail(f"Failed to run: {' '.join(cmd)!r}\n{ret}")


def setup_debian(
    container, os_version, os_codename, root_url, salt_release, downloads_path
):
    setup_debian_family(
        container,
        os_version,
        os_codename,
        root_url,
        salt_release,
        downloads_path,
        "debian",
    )


def setup_ubuntu(
    container, os_version, os_codename, root_url, salt_release, downloads_path
):
    setup_debian_family(
        container,
        os_version,
        os_codename,
        root_url,
        salt_release,
        downloads_path,
        "ubuntu",
    )


@pytest.fixture(scope="module")
def setup_macos(root_url, salt_release, shell):

    arch = os.environ.get("SALT_REPO_ARCH") or "x86_64"
    if arch == "aarch64":
        arch = "arm64"

    repo_type = os.environ.get("SALT_REPO_TYPE", "staging")
    if packaging.version.parse(salt_release) > packaging.version.parse("3005"):
        if repo_type == "staging":
            mac_pkg = f"salt-{salt_release}-py3-{arch}-unsigned.pkg"
        else:
            mac_pkg = f"salt-{salt_release}-py3-{arch}.pkg"
        mac_pkg_url = f"{root_url}/macos/minor/{salt_release}/{mac_pkg}"
    else:
        mac_pkg_url = f"{root_url}/macos/{salt_release}/{mac_pkg}"
        mac_pkg = f"salt-{salt_release}-macos-{arch}.pkg"

    mac_pkg_path = f"/tmp/{mac_pkg}"
    pytest.helpers.download_file(mac_pkg_url, f"/tmp/{mac_pkg}")

    ret = shell.run(
        "installer",
        "-pkg",
        mac_pkg_path,
        "-target",
        "/",
        check=False,
    )
    assert ret.returncode == 0, ret

    yield


@pytest.fixture(scope="module")
def setup_windows(root_url, salt_release, shell):

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

    pkg_path = pathlib.Path(r"C:\TEMP", win_pkg)
    pkg_path.parent.mkdir(exist_ok=True)

    pytest.helpers.download_file(win_pkg_url, pkg_path)
    ret = shell.run(pkg_path, "/start-minion=0", "/S", check=False)
    assert ret.returncode == 0

    log.debug("Removing installed salt-minion service")
    ret = shell.run(
        "cmd", "/c", str(ssm_bin), "remove", "salt-minion", "confirm", check=False
    )
    assert ret.returncode == 0, ret


@pytest.mark.skip_unless_on_linux
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
@pytest.mark.skip_if_binaries_missing("dockerd")
def test_download_linux(salt_test_command, pkg_container, root_url, salt_release):
    """
    Test downloading of Salt packages and running various commands on Linux hosts
    """
    res = pkg_container.container.run(salt_test_command)
    assert res.returncode == 0


@pytest.mark.skip_unless_on_darwin
@pytest.mark.usefixtures("setup_macos")
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download_macos(salt_test_command, shell):
    """
    Test downloading of Salt packages and running various commands on Mac OS hosts
    """
    _cmd = salt_test_command.split()
    ret = shell.run(*_cmd, check=False)
    assert ret.returncode == 0, ret


@pytest.mark.skip_unless_on_windows
@pytest.mark.usefixtures("setup_windows")
@pytest.mark.parametrize("salt_test_command", get_salt_test_commands())
def test_download_windows(salt_test_command, shell):
    """
    Test downloading of Salt packages and running various commands on Windows hosts
    """
    _cmd = salt_test_command.split()
    root_dir = pathlib.Path(r"C:\Program Files\Salt Project\Salt")
    _cmd[0] = str(root_dir / _cmd[0])

    ret = shell.run(*_cmd, check=False)
    assert ret.returncode == 0, ret
