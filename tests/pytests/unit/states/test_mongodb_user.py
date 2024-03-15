"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.mongodb
import salt.states.mongodb_user as mongodb_user
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    salt.modules.mongodb.pymongo = MagicMock()
    salt.modules.mongodb.pymongo.errors.PyMongoError = Exception
    salt.modules.mongodb.HAS_MONGODB = True
    fake_config = {
        "mongodb.host": "example.com",
        "mongodb.port": 42,
    }
    fake_salt = {
        "mongodb.user_exists": salt.modules.mongodb.user_exists,
        "mongodb.user_find": salt.modules.mongodb.user_find,
        "mongodb.user_create": salt.modules.mongodb.user_create,
        "mongodb.user_remove": salt.modules.mongodb.user_remove,
        "config.option": fake_config.get,
    }
    with patch("salt.modules.mongodb._version", autospec=True, return_value=4):
        yield {
            mongodb_user: {
                "__opts__": {"test": True},
                "__salt__": fake_salt,
            },
            salt.modules.mongodb: {"__salt__": fake_salt},
        }


def test_present():
    """
    Test to ensure that the user is present with the specified properties.
    """
    name = "myapp"
    passwd = "password-of-myapp"

    comt = "Port ({1, 2, 3}) is not an integer."
    ret = {"name": name, "result": False, "comment": comt, "changes": {}}

    assert mongodb_user.present(name, passwd, port={1, 2, 3}) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=[])
    with patch.dict(
        mongodb_user.__salt__,
        {"mongodb.user_create": mock_t, "mongodb.user_find": mock_f},
    ):
        comt = ("User {} is not present and needs to be created").format(name)
        ret.update({"comment": comt, "result": None})
        assert mongodb_user.present(name, passwd) == ret

        with patch.dict(mongodb_user.__opts__, {"test": True}):
            comt = f"User {name} is not present and needs to be created"
            ret.update({"comment": comt, "result": None})
            assert mongodb_user.present(name, passwd) == ret

        with patch.dict(mongodb_user.__opts__, {"test": False}):
            comt = f"User {name} has been created"
            ret.update({"comment": comt, "result": True, "changes": {name: "Present"}})
            assert mongodb_user.present(name, passwd) == ret


def test_absent():
    """
    Test to ensure that the named user is absent.
    """
    name = "myapp"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[True, True, False])
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        mongodb_user.__salt__,
        {"mongodb.user_exists": mock, "mongodb.user_remove": mock_t},
    ):
        with patch.dict(mongodb_user.__opts__, {"test": True}):
            comt = f"User {name} is present and needs to be removed"
            ret.update({"comment": comt, "result": None})
            assert mongodb_user.absent(name) == ret

        with patch.dict(mongodb_user.__opts__, {"test": False}):
            comt = f"User {name} has been removed"
            ret.update({"comment": comt, "result": True, "changes": {name: "Absent"}})
            assert mongodb_user.absent(name) == ret

        comt = f"User {name} is not present"
        ret.update({"comment": comt, "result": True, "changes": {}})
        assert mongodb_user.absent(name) == ret


@pytest.mark.parametrize(
    "expected_ssl, expected_allow_invalid, absent_kwargs",
    [
        (True, False, {"name": "mr_fnord", "ssl": True}),
        (True, False, {"name": "mr_fnord", "ssl": True, "verify_ssl": None}),
        (True, False, {"name": "mr_fnord", "ssl": True, "verify_ssl": True}),
        (True, True, {"name": "mr_fnord", "ssl": True, "verify_ssl": False}),
        (False, False, {"name": "mr_fnord", "ssl": False, "verify_ssl": True}),
        (False, True, {"name": "mr_fnord", "ssl": None, "verify_ssl": False}),
        (False, False, {"name": "mr_fnord"}),
        (False, False, {"name": "mr_fnord", "verify_ssl": True}),
        (False, True, {"name": "mr_fnord", "verify_ssl": False}),
    ],
)
def test_when_absent_is_called_it_should_pass_the_correct_ssl_argument_to_MongoClient(
    expected_ssl, expected_allow_invalid, absent_kwargs
):
    with patch.dict(mongodb_user.__opts__, {"test": False}), patch(
        "salt.modules.mongodb.Version", autospec=True, return_value=4
    ):
        salt.modules.mongodb.pymongo.database.Database.return_value.command.return_value = {
            "users": [
                {
                    "user": absent_kwargs["name"],
                    "roles": [{"db": "kaiser"}, {"db": "dinner"}],
                }
            ]
        }
        mongodb_user.absent(**absent_kwargs)
        salt.modules.mongodb.pymongo.MongoClient.assert_has_calls(
            [
                call(
                    host="example.com",
                    port=42,
                    username=None,
                    password=None,
                    authSource="admin",
                    ssl=expected_ssl,
                    tlsAllowInvalidCertificates=expected_allow_invalid,
                ),
                call().__bool__(),  # pylint: disable=unnecessary-dunder-call
                call(
                    host="example.com",
                    port=42,
                    username=None,
                    password=None,
                    authSource="admin",
                    ssl=expected_ssl,
                    tlsAllowInvalidCertificates=expected_allow_invalid,
                ),
                call().__bool__(),  # pylint: disable=unnecessary-dunder-call
            ]
        )


# tlsAllowInvalidCertificates will be `not verify_ssl` - verify_ss is a much
# more common argument in Salt than tlsAllowInvalidCertificates.
@pytest.mark.parametrize(
    "expected_ssl, expected_allow_invalid, present_kwargs",
    [
        (True, False, {"name": "mr_fnord", "ssl": True}),
        (True, False, {"name": "mr_fnord", "ssl": True, "verify_ssl": None}),
        (True, False, {"name": "mr_fnord", "ssl": True, "verify_ssl": True}),
        (True, True, {"name": "mr_fnord", "ssl": True, "verify_ssl": False}),
        (False, False, {"name": "mr_fnord", "ssl": False, "verify_ssl": True}),
        (False, True, {"name": "mr_fnord", "ssl": None, "verify_ssl": False}),
        (False, False, {"name": "mr_fnord"}),
        (False, False, {"name": "mr_fnord", "verify_ssl": True}),
        (False, True, {"name": "mr_fnord", "verify_ssl": False}),
    ],
)
@pytest.mark.parametrize(
    "users",
    [[], [{"roles": [{"db": "kaiser"}, {"db": "fnord"}]}]],
)
def test_when_present_is_called_it_should_pass_the_correct_ssl_argument_to_MongoClient(
    expected_ssl, expected_allow_invalid, present_kwargs, users
):
    with patch.dict(mongodb_user.__opts__, {"test": False}):
        salt.modules.mongodb.pymongo.database.Database.return_value.command.return_value = {
            "users": users
        }
        mongodb_user.present(passwd="fnord", **present_kwargs)
        salt.modules.mongodb.pymongo.MongoClient.assert_has_calls(
            [
                call(
                    host="example.com",
                    port=42,
                    username=None,
                    password=None,
                    authSource="admin",
                    ssl=expected_ssl,
                    tlsAllowInvalidCertificates=expected_allow_invalid,
                ),
                call().__bool__(),  # pylint: disable=unnecessary-dunder-call
                call(
                    host="example.com",
                    port=42,
                    username=None,
                    password=None,
                    authSource="admin",
                    ssl=expected_ssl,
                    tlsAllowInvalidCertificates=expected_allow_invalid,
                ),
                call().__bool__(),  # pylint: disable=unnecessary-dunder-call
            ]
        )
