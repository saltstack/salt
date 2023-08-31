"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.modules.esxcluster
"""

import pytest

import salt.modules.esxcluster as esxcluster
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {esxcluster: {"__proxy__": {}}}


def test_get_details():
    mock_get_details = MagicMock()
    with patch.dict(esxcluster.__proxy__, {"esxcluster.get_details": mock_get_details}):
        esxcluster.get_details()
    mock_get_details.assert_called_once_with()
