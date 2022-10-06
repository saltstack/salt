"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import pytest

import salt.modules.mongodb as mongodb
from tests.support.mock import MagicMock, patch

try:
    import pymongo  # pylint: disable=unused-import

    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(not HAS_PYMONGO, reason="No python mongo client installed."),
]


class MockMongoConnect:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def list_database_names(self, *args, **kwards):
        return []

    def drop_database(self, *args, **kwards):
        return True


class MockPyMongoDatabase:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def authenticate(self, *args, **kwards):
        return True

    def command(self, *args, **kwards):
        return ""

    def create_collection(self, *args, **kwards):
        return True

    def list_collection_names(self, *args, **kwards):
        return []


@pytest.fixture
def configure_loader_modules():
    return {mongodb: {}}


def test_version():
    """
    Test mongodb.version
    """
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        database_command_mock = MagicMock(return_value={"version": "6.0.2"})
        with patch.object(MockPyMongoDatabase, "command", database_command_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.version()
                    assert ret == "6.0.2"


def test_db_list():
    """
    Test mongodb.db_list
    """
    list_db_names_mock = MagicMock(return_value=["admin", "config", "local"])

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    with patch.object(MockMongoConnect, "list_database_names", list_db_names_mock):
        mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
        with patch("pymongo.MongoClient", mongodb_client_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.db_list()
                    assert ret == ["admin", "config", "local"]


def test_db_exists():
    """
    Test mongodb.db_exists
    """
    list_db_names_mock = MagicMock(return_value=["admin", "config", "local"])

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    with patch.object(MockMongoConnect, "list_database_names", list_db_names_mock):
        mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
        with patch("pymongo.MongoClient", mongodb_client_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.db_exists("admin")
                    assert ret


def test_user_list():
    """
    Test mongodb.user_list
    """
    user_info = {
        "users": [
            {
                "_id": "admin.test_user",
                "userId": "",
                "user": "test_user",
                "db": "admin",
                "roles": [{"role": "read", "db": "admin"}],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
            {
                "_id": "admin.test_user2",
                "userId": "",
                "user": "test_user2",
                "db": "admin",
                "roles": [],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
        ],
        "ok": 1.0,
    }

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        database_version = {"version": "6.0.2"}
        with patch.object(
            MockPyMongoDatabase,
            "command",
            MagicMock(side_effect=[database_version, user_info]),
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_list()
                    expected = [
                        {
                            "user": "test_user",
                            "roles": [{"role": "read", "db": "admin"}],
                        },
                        {"user": "test_user2", "roles": []},
                    ]
                    assert ret == expected


def test_user_exists():
    """
    Test mongodb.user_exists
    """
    user_info = {
        "users": [
            {
                "_id": "admin.test_user",
                "userId": "",
                "user": "test_user",
                "db": "admin",
                "roles": [{"role": "read", "db": "admin"}],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
            {
                "_id": "admin.test_user2",
                "userId": "",
                "user": "test_user2",
                "db": "admin",
                "roles": [],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
        ],
        "ok": 1.0,
    }

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        database_version = {"version": "6.0.2"}
        with patch.object(
            MockPyMongoDatabase,
            "command",
            MagicMock(side_effect=[database_version, user_info]),
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_exists("test_user")
                    assert ret

    with patch("pymongo.MongoClient", mongodb_client_mock):
        database_version = {"version": "6.0.2"}
        with patch.object(
            MockPyMongoDatabase,
            "command",
            MagicMock(side_effect=[database_version, user_info]),
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):

                    ret = mongodb.user_exists("no_test_user")
                    assert not ret


def test_user_create():
    """
    Test mongodb.user_create
    """
    user_create_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(MockPyMongoDatabase, "command", user_create_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_create("test_user", "test_password")
                    assert ret


def test_user_remove():
    """
    Test mongodb.user_remove
    """
    user_remove_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(MockPyMongoDatabase, "command", user_remove_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_remove("test_user")
                    assert ret


def test_user_roles_exists():
    """
    Test mongodb.user_roles_exist
    """
    user_info = {
        "users": [
            {
                "_id": "admin.test_user",
                "userId": "",
                "user": "test_user",
                "db": "admin",
                "roles": [{"role": "read", "db": "admin"}],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
            {
                "_id": "admin.test_user2",
                "userId": "",
                "user": "test_user2",
                "db": "admin",
                "roles": [],
                "mechanisms": ["SCRAM-SHA-1", "SCRAM-SHA-256"],
            },
        ],
        "ok": 1.0,
    }

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        database_version = {"version": "6.0.2"}
        with patch.object(
            MockPyMongoDatabase,
            "command",
            MagicMock(side_effect=[database_version, user_info]),
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_roles_exists("test_user", '["read"]', "admin")
                    assert ret


def test_user_grant_roles():
    """
    Test mongodb.user_remove
    """
    user_grant_roles_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(MockPyMongoDatabase, "command", user_grant_roles_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_grant_roles(
                        "test_user", '[{"role": "readWrite", "db": "admin" }]', "admin"
                    )
                    assert ret


def test_user_revoke_roles():
    """
    Test mongodb.user_remove
    """
    user_revoke_roles_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(MockPyMongoDatabase, "command", user_revoke_roles_mock):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.user_revoke_roles(
                        "test_user", '[{"role": "readWrite", "db": "admin" }]', "admin"
                    )
                    assert ret


def test_collection_create():
    """
    Test mongodb.user_create
    """
    collection_create_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(
            MockPyMongoDatabase, "create_collection", collection_create_mock
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.collection_create("test_collection")
                    assert ret


def test_collections_list():
    """
    Test mongodb.collections_list
    """
    collections_list = ["system.users", "mycollection", "system.version"]

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    with patch("pymongo.MongoClient", mongodb_client_mock):
        with patch.object(
            MockPyMongoDatabase,
            "list_collection_names",
            MagicMock(return_value=collections_list),
        ):
            with patch("pymongo.database.Database", pymongo_database_mock):
                config_option_mock = MagicMock(
                    side_effect=["user", "password", "localhost", "27017"]
                )
                with patch.dict(
                    mongodb.__salt__, {"config.option": config_option_mock}
                ):
                    ret = mongodb.collections_list()
                    assert ret == ["system.users", "mycollection", "system.version"]
