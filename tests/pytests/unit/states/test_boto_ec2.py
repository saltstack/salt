"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.boto_ec2 as boto_ec2
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {boto_ec2: {}}


def test_key_present():
    """
    Test to ensure key pair is present.
    """
    name = "mykeypair"
    upublic = "salt://mybase/public_key.pub"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False, False])
    mock_bool = MagicMock(side_effect=[IOError, True])
    with patch.dict(
        boto_ec2.__salt__, {"boto_ec2.get_key": mock, "cp.get_file_str": mock_bool}
    ):
        comt = "The key name {} already exists".format(name)
        ret.update({"comment": comt})
        assert boto_ec2.key_present(name) == ret

        comt = "File {} not found.".format(upublic)
        ret.update({"comment": comt, "result": False})
        assert boto_ec2.key_present(name, upload_public=upublic) == ret

        with patch.dict(boto_ec2.__opts__, {"test": True}):
            comt = "The key {} is set to be created.".format(name)
            ret.update({"comment": comt, "result": None})
            assert boto_ec2.key_present(name, upload_public=upublic) == ret


def test_key_absent():
    """
    Test to delete a key pair
    """
    name = "new_table"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(boto_ec2.__salt__, {"boto_ec2.get_key": mock}):
        comt = "The key name {} does not exist".format(name)
        ret.update({"comment": comt})
        assert boto_ec2.key_absent(name) == ret

        with patch.dict(boto_ec2.__opts__, {"test": True}):
            comt = "The key {} is set to be deleted.".format(name)
            ret.update({"comment": comt, "result": None})
            assert boto_ec2.key_absent(name) == ret
