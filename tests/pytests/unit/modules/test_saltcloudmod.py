"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.modules.saltcloudmod as saltcloudmod
import salt.utils.json
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {saltcloudmod: {}}


def test_create():
    """
    Test if create the named vm
    """
    mock = MagicMock(return_value="""{"foo": "bar"}""")
    mock_json_loads = MagicMock(side_effect=ValueError())
    with patch.dict(saltcloudmod.__salt__, {"cmd.run_stdout": mock}):
        assert saltcloudmod.create("webserver", "rackspace_centos_512")

        with patch.object(salt.utils.json, "loads", mock_json_loads):
            assert saltcloudmod.create("webserver", "rackspace_centos_512") == {}
