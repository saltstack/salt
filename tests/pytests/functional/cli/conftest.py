import pytest


@pytest.fixture(scope="package")
def salt_cloud_cli(salt_master_factory):
    """
    The ``salt-cloud`` CLI as a fixture against the configured master
    """
    return salt_master_factory.salt_cloud_cli()


@pytest.fixture(scope="package")
def salt_spm_cli(salt_master_factory):
    """
    The ``spm`` CLI as a fixture against the configured master
    """
    return salt_master_factory.salt_spm_cli()
