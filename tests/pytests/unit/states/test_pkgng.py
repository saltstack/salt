"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.pkgng as pkgng
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pkgng: {}}


def test_update_packaging_site():
    """
    Test to execute update_packaging_site.
    """
    name = "http://192.168.0.2"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_t = MagicMock(return_value=True)
    with patch.dict(pkgng.__salt__, {"pkgng.update_package_site": mock_t}):
        assert pkgng.update_packaging_site(name) == ret
