import logging
import os
import re

import requests

import salt.utils.files
import salt.utils.hashutils
import salt.utils.http
import salt.utils.thin

log = logging.getLogger(__name__)

BASE_URL = "https://packages.broadcom.com/artifactory/saltproject-generic/onedir/"


def gen_relenv(
    cachedir,
    kernel,
    os_arch,
    overwrite=False,
    base_url=BASE_URL,
):
    """
    Deploy salt-relenv.
    :param cachedir: The cache directory where the downloaded tarball will be stored.
    :param kernel: The detected OS (e.g., 'linux', 'darwin', 'windows').
    :param os_arch: The detected architecture (e.g., 'amd64', 'x86_64', 'arm64').
    :param overwrite: Whether to overwrite the existing cached tarball.
    :return: The path to the recompressed .tgz file.
    """
    version = get_latest_version(base_url)

    # Set up directories
    relenv_dir = os.path.join(cachedir, "relenv", version, kernel, os_arch)
    if not os.path.isdir(relenv_dir):
        os.makedirs(relenv_dir)

    relenv_url = get_tarball(f"{base_url}/{version}/", kernel, os_arch)
    tarball_path = os.path.join(relenv_dir, "salt-relenv.tar.xz")

    # Download the tarball if it doesn't exist or overwrite is True
    if overwrite or not os.path.exists(tarball_path):
        if not download(relenv_url, tarball_path):
            return False

    return tarball_path


def get_tarball(base_url, kernel, arch):
    """
    Get the latest Salt onedir tarball URL for the specified kernel and architecture.
    :param base_url: The artifactory location
    :param kernel: The detected OS (e.g., 'linux', 'darwin', 'windows').
    :param arch: The detected architecture (e.g., 'amd64', 'x86_64', 'arm64').
    :return: The URL of the latest tarball.
    """

    try:
        # Request the page listing
        response = requests.get(base_url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Failed to retrieve tarball listing: {e}")
        raise ValueError("Unable to fetch tarball list from repository")

    latest = sorted(re.findall(r"3\d\d\d\.\d", response.text))[-1]

    try:
        # Request the page listing
        response = requests.get(f"{base_url}/{latest}", timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Failed to retrieve tarball listing: {e}")
        raise ValueError("Unable to fetch tarball list from repository")

    # Search for tarball filenames that match the kernel and arch
    pattern = re.compile(rf'href="(salt-.*-onedir-{kernel}-{arch}\.tar\.xz)"')
    matches = pattern.findall(response.text)
    if not matches:
        log.error(f"No tarballs found for {kernel} and {arch}")
        raise ValueError(f"No tarball found for {kernel} {arch}")

    # Return the latest tarball URL
    matches.sort()
    latest_tarball = matches[-1]
    return f"{base_url}/{latest}/{latest_tarball}"


def get_latest_version(base_url):
    """
    Retrieve the latest version from the base artifactory directory
    :param base_url: The artifactory location
    :return: The version number of the latest artifact
    """
    try:
        response = requests.get(base_url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Failed to retrieve directory listing: {e}")
        raise ValueError("Unable to fetch directory list from repository")

    # Extract version numbers from hrefs
    pattern = re.compile(r'href="(\d+\.\d+)/"')
    versions = pattern.findall(response.text)

    if not versions:
        log.error("No versions found in directory listing")
        raise ValueError("No versions found in directory listing")

    # Sort versions numerically and return the latest one
    versions.sort(key=lambda s: list(map(int, s.split("."))), reverse=True)
    return versions[0]


def download(url, destination):
    """
    Download the salt artifact from the given destination to the cache.
    :param url: The artifact location
    :param destination: Path to the downloaded file
    :return: True if the download was successful, else False
    """
    if not os.path.exists(destination):
        log.info(f"Downloading from {url} to {destination}")
        with salt.utils.files.fopen(destination, "wb+") as dest_file:
            result = salt.utils.http.query(
                url=url,
                method="GET",
                stream=True,
                streaming_callback=dest_file.write,
                raise_error=True,
            )
            if result.get("status") != 200:
                log.error(f"Failed to download file from {url}")
                return False
    return True
