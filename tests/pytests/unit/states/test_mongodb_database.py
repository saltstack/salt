"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.mongodb
import salt.states.mongodb_database as mongodb_database
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    salt.modules.mongodb.pymongo = MagicMock()
    salt.modules.mongodb.pymongo.errors.PyMongoError = Exception
    salt.modules.mongodb.HAS_MONGODB = True
    fake_config = {
        "mongodb.host": "mongodb.example.net",
        "mongodb.port": 1982,
    }
    fake_salt = {
        "mongodb.db_exists": salt.modules.mongodb.db_exists,
        "mongodb.db_remove": salt.modules.mongodb.db_remove,
        "config.option": fake_config.get,
    }
    with patch("salt.modules.mongodb._version", autospec=True, return_value=4):
        yield {
            mongodb_database: {"__salt__": fake_salt, "__opts__": {"test": False}},
            salt.modules.mongodb: {"__salt__": fake_salt},
        }


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
            comt = f"Database {name} is present and needs to be removed"
            ret.update({"comment": comt})
            assert mongodb_database.absent(name) == ret

        with patch.dict(mongodb_database.__opts__, {"test": False}):
            comt = f"Database {name} has been removed"
            ret.update({"comment": comt, "result": True, "changes": {"mydb": "Absent"}})
            assert mongodb_database.absent(name) == ret

            comt = f"Database {name} is not present"
            ret.update({"comment": comt, "changes": {}})
            assert mongodb_database.absent(name) == ret


@pytest.mark.parametrize(
    "expected_ssl, expected_allow_invalid, absent_kwargs",
    [
        (True, False, {"name": "some_database", "ssl": True}),
        (True, False, {"name": "some_database", "ssl": True, "verify_ssl": None}),
        (True, False, {"name": "some_database", "ssl": True, "verify_ssl": True}),
        (True, True, {"name": "some_database", "ssl": True, "verify_ssl": False}),
        (False, False, {"name": "some_database", "ssl": False}),
        (False, False, {"name": "some_database", "ssl": None}),
        (False, False, {"name": "some_database"}),
        (False, False, {"name": "some_database", "verify_ssl": None}),
        (False, False, {"name": "some_database", "verify_ssl": True}),
        (False, True, {"name": "some_database", "verify_ssl": False}),
    ],
)
def test_when_mongodb_database_remove_is_called_it_should_correctly_pass_ssl_argument(
    expected_ssl, expected_allow_invalid, absent_kwargs
):
    # database from params needs to be in this return_value
    salt.modules.mongodb.pymongo.MongoClient.return_value.list_database_names.return_value = [
        "foo",
        "bar",
        "some_database",
    ]
    mongodb_database.absent(**absent_kwargs)
    salt.modules.mongodb.pymongo.MongoClient.assert_has_calls(
        [
            call(
                host="mongodb.example.net",
                port=1982,
                username=None,
                password=None,
                authSource="admin",
                ssl=expected_ssl,
                tlsAllowInvalidCertificates=expected_allow_invalid,
            ),
            call().__bool__(),  # pylint: disable=unnecessary-dunder-call
            # Not sure why database_names is in the call list given our
            # return_value modifications above - it *should* have removed that
            # from the mock call list, but it didn't. There's probably some
            # other way to ensure that database_names/drop_database is out of
            # the MongoClient mock call list, but it was taking too long.
            call().list_database_names(),
            call(
                host="mongodb.example.net",
                port=1982,
                username=None,
                password=None,
                authSource="admin",
                ssl=expected_ssl,
                tlsAllowInvalidCertificates=expected_allow_invalid,
            ),
            call().__bool__(),  # pylint: disable=unnecessary-dunder-call
            call().drop_database("some_database"),
        ]
    )
