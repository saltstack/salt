import pytest
import salt.modules.cohesity as cohesity


@pytest.fixture
def configure_loader_modules():
    return {cohesity: {}}
