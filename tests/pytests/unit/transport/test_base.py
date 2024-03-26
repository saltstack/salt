"""
Unit tests for salt.transport.base.
"""

import pytest

import salt.transport.base

pytestmark = [
    pytest.mark.core_test,
]


def test_unclosed_warning():

    transport = salt.transport.base.Transport()
    assert transport._closing is False
    assert transport._connect_called is False
    transport.connect()
    assert transport._connect_called is True
    with pytest.warns(salt.transport.base.TransportWarning):
        del transport
