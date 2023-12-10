"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>

    Test cases for salt.modules.nfs3
"""


import pytest

import salt.modules.nfs3 as nfs3
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {nfs3: {}}


def test_list_exports():
    """
    Test for List configured exports
    """
    with patch("salt.utils.files.fopen", mock_open(read_data="A B1(23")):
        exports = nfs3.list_exports()
        assert exports == {"A": [{"hosts": "B1", "options": ["23"]}]}, exports


def test_del_export():
    """
    Test for Remove an export
    """
    list_exports_mock = MagicMock(
        return_value={"A": [{"hosts": ["B1"], "options": ["23"]}]}
    )
    with patch.object(nfs3, "list_exports", list_exports_mock), patch.object(
        nfs3, "_write_exports", MagicMock(return_value=None)
    ):
        result = nfs3.del_export(path="A")
        assert result == {}, result
