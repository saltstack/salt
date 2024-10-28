import logging
import os
import re

import requests

import salt.utils.files
import salt.utils.hashutils
import salt.utils.http
import salt.utils.thin

log = logging.getLogger(__name__)


def gen_relenv(
    cachedir,
    kernel,
    os_arch,
    overwrite=False,
):
    """
    Deploy salt-relenv.
    :param cachedir: The cache directory where the downloaded tarball will be stored.
    :param kernel: The detected OS (e.g., 'linux', 'darwin', 'windows').
    :param os_arch: The detected architecture (e.g., 'amd64', 'x86_64', 'arm64').
    :param overwrite: Whether to overwrite the existing cached tarball.
    :return: The path to the recompressed .tgz file.
    """
    # Set up directories
    relenv_dir = os.path.join(cachedir, "relenv", kernel, os_arch)
    if not os.path.isdir(relenv_dir):
        os.makedirs(relenv_dir)

    relenv_url = get_tarball(kernel, os_arch)
    tarball_path = os.path.join(relenv_dir, "salt-relenv.tar.xz")

    # Download the tarball if it doesn't exist or overwrite is True
    if overwrite or not os.path.exists(tarball_path):
        if not download(cachedir, relenv_url, tarball_path):
            return False

    return tarball_path


def get_tarball(kernel, arch):
    """
    Get the latest Salt onedir tarball URL for the specified kernel and architecture.
    :param kernel: The detected OS (e.g., 'linux', 'darwin', 'windows').
    :param arch: The detected architecture (e.g., 'amd64', 'x86_64', 'arm64').
    :return: The URL of the latest tarball.
    """
    base_url = "https://repo.saltproject.io/salt/py3/onedir/latest/"
    try:
        # Request the page listing
        response = requests.get(base_url, timeout=60)
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
    return base_url + latest_tarball


def download(cachedir, url, destination):
    """
    Download the salt artifact from the given destination to the cache.
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
