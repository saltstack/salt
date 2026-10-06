"""
Fixtures for WebSocket transport functional tests.
"""

# pylint: disable=unused-import

import pytest

import salt.utils.process

# Import SSL certificate fixtures  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_ca_cert_key  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_client_cert_key  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_invalid_ca_cert_key  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_invalid_client_cert_key  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_invalid_server_cert_key  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_master_config  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_minion_config  # noqa: F401
from tests.support.pytest.transport_ssl import ssl_minion_config_no_cert  # noqa: F401
from tests.support.pytest.transport_ssl import (  # noqa: F401; noqa: F401; noqa: F401
    ssl_master_config_invalid_cert,
    ssl_minion_config_invalid_cert,
    ssl_server_cert_key,
)


@pytest.fixture
def process_manager():
    """Process manager for transport tests."""
    pm = salt.utils.process.ProcessManager()
    try:
        yield pm
    finally:
        pm.terminate()
