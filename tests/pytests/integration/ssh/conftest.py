import pytest

from tests.support.pytest.helpers import reap_stray_processes


@pytest.fixture(scope="package", autouse=True)
def _auto_skip_on_fedora_39(grains):
    if grains["osfinger"] == "Fedora Linux-39":
        pytest.skip(
            "Fedora 39 ships with Python 3.12. Test can't run with system Python on 3.12"
            # Actually, the problem is that the tornado we ship is not prepared for Python 3.12,
            # and it imports `ssl` and checks if the `match_hostname` function is defined, which
            # has been deprecated since Python 3.7, so, the logic goes into trying to import
            # backports.ssl-match-hostname which is not installed on the system.
        )


@pytest.fixture(autouse=True)
def _reap_stray_processes(grains):
    # when tests timeout, we migth leave child processes behind
    # nuke them
    with reap_stray_processes():
        # Run test
        yield
