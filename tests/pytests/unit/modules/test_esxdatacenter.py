"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.modules.esxdatacenter
"""

import pytest

import salt.modules.esxdatacenter as esxdatacenter
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {esxdatacenter: {"__proxy__": {}}}


def test_get_details():
    mock_get_details = MagicMock()
    with patch.dict(
        esxdatacenter.__proxy__, {"esxdatacenter.get_details": mock_get_details}
    ):
        esxdatacenter.get_details()
    mock_get_details.assert_called_once_with()
