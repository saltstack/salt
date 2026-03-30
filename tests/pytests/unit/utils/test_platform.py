import multiprocessing
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


def test_spawning_platform_spawn():
    """
    spawning_platform() must return True when the multiprocessing start method
    is "spawn" (Windows default, macOS default on Python >= 3.8).
    """
    with patch.object(multiprocessing, "get_start_method", return_value="spawn"):
        assert salt.utils.platform.spawning_platform() is True


def test_spawning_platform_forkserver():
    """
    spawning_platform() must return True when the multiprocessing start method
    is "forkserver".  Like "spawn", forkserver transfers the Process object to
    the child via pickle, so Salt must prepare __getstate__/__setstate__ for it.
    This is the Linux default starting with Python 3.14.
    """
    with patch.object(multiprocessing, "get_start_method", return_value="forkserver"):
        assert salt.utils.platform.spawning_platform() is True


def test_spawning_platform_fork():
    """
    spawning_platform() must return False when the multiprocessing start method
    is "fork" (Linux default on Python < 3.14).  Fork inherits process state
    directly, so pickling is not required.
    """
    with patch.object(multiprocessing, "get_start_method", return_value="fork"):
        assert salt.utils.platform.spawning_platform() is False
