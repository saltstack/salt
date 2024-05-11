import pytest

from tests.support.pytest.helpers import reap_stray_processes


@pytest.fixture(scope="package", autouse=True)
def _auto_skip_on_system_python_too_recent(grains):
    if (
        grains["osfinger"] in ("Fedora Linux-40", "Ubuntu-24.04")
        or grains["os_family"] == "Arch"
    ):
        pytest.skip(
            "System ships with a version of python that is too recent for salt-ssh tests",
            # Actually, the problem is that the tornado we ship is not prepared for Python 3.12,
            # and it imports `ssl` and checks if the `match_hostname` function is defined, which
            # has been deprecated since Python 3.7, so, the logic goes into trying to import
            # backports.ssl-match-hostname which is not installed on the system.
        )


@pytest.fixture(autouse=True)
def _reap_stray_processes():
    # when tests timeout, we migth leave child processes behind
    # nuke them
    with reap_stray_processes():
        # Run test
        yield
