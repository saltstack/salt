"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.mongodb_database as mongodb_database
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {mongodb_database: {}}


def test_absent():
    """
    Test to ensure that the named database is absent.
    """
    name = "mydb"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, False])
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        mongodb_database.__salt__,
        {"mongodb.db_exists": mock, "mongodb.db_remove": mock_t},
    ):
        with patch.dict(mongodb_database.__opts__, {"test": True}):
            comt = "Database {} is present and needs to be removed".format(name)
            ret.update({"comment": comt})
            assert mongodb_database.absent(name) == ret

        with patch.dict(mongodb_database.__opts__, {"test": False}):
            comt = "Database {} has been removed".format(name)
            ret.update({"comment": comt, "result": True, "changes": {"mydb": "Absent"}})
            assert mongodb_database.absent(name) == ret

            comt = "Database {} is not present".format(name)
            ret.update({"comment": comt, "changes": {}})
            assert mongodb_database.absent(name) == ret
