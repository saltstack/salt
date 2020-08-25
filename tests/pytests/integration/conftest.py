import pytest


@pytest.fixture(scope="package")
def salt_master(request, salt_factories):
    return salt_factories.spawn_master(request, "master")
