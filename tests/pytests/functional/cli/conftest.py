import pytest


@pytest.fixture(scope="package")
def salt_cloud_cli(salt_master_factory):
    """
    The ``salt-cloud`` CLI as a fixture against the running master
    """
    return salt_master_factory.get_salt_cloud_cli()
