"""
Fixtures for unit transport tests.
"""

# pylint: disable=unused-import

import pytest  # noqa: F401

# Import SSL certificate fixtures
from tests.support.pytest.transport_ssl import (
    ssl_ca_cert_key,
    ssl_client_cert_key,
    ssl_master_config,
    ssl_minion_a_cert_key,
    ssl_minion_a_config,
    ssl_minion_b_cert_key,
    ssl_minion_b_config,
    ssl_minion_cert_key_with_id,
    ssl_minion_config,
    ssl_server_cert_key,
)
