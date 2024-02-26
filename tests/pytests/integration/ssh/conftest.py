import pytest


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
