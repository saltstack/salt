"""
    tests.integration.proxy.conftest
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Proxy related fixtures
"""

import logging

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="package", autouse=True)
def salt_proxy(salt_proxy):
    return salt_proxy
