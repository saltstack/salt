import subprocess

import salt.utils.platform
from tests.support.mock import patch


def test_linux_distribution():
    """
    Test that when `distro` fails with a `subprocess.CalledProcessError` salt
    returns empty strings as default values.
    """
    distro_name = "Salt"
    distro_version = "1"
    distro_codename = "Awesome"
    with patch("distro.name", return_value=distro_name):
        with patch("distro.version", return_value=distro_version), patch(
            "distro.codename", return_value=distro_codename
        ):
            assert salt.utils.platform.linux_distribution() == (
                distro_name,
                distro_version,
                distro_codename,
            )

        distro_version = ""
        with patch(
            "distro.version",
            side_effect=subprocess.CalledProcessError(returncode=1, cmd=["foo"]),
        ), patch("distro.codename", return_value=distro_codename):
            assert salt.utils.platform.linux_distribution() == (
                distro_name,
                distro_version,
                distro_codename,
            )
        distro_codename = ""
        with patch(
            "distro.version",
            side_effect=subprocess.CalledProcessError(returncode=1, cmd=["foo"]),
        ), patch(
            "distro.codename",
            side_effect=subprocess.CalledProcessError(returncode=1, cmd=["foo"]),
        ):
            assert salt.utils.platform.linux_distribution() == (
                distro_name,
                distro_version,
                distro_codename,
            )
