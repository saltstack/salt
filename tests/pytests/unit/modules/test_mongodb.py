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


class MockInsertResult:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.inserted_ids = []
        self.acknowledged = True


class MockDeleteResult:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.deleted_count = 0
        self.raw_result = {}
        self.acknowledged = True


class MockPyMongoDatabase:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.my_collection = None

    def authenticate(self, *args, **kwards):
        return True

    def command(self, *args, **kwards):
        return ""

    def create_collection(self, *args, **kwards):
        return True

    def list_collection_names(self, *args, **kwards):
        return []


class MockPyMongoCollection:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def find(self, *args, **kwards):
        return []

    def insert_many(self, *args, **kwards):
        return True

    def delete_one(self, *args, **kwards):
        return True


@pytest.fixture
def configure_loader_modules():
    return {mongodb: {}}


def test_version():
    """
    Test mongodb.version
    """
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    database_command_mock = MagicMock(autospec=True, return_value={"version": "6.0.2"})
    config_option_mock = MagicMock(
        side_effect=["user", "password", "localhost", "27017"]
    )

    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", database_command_mock
    )
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_command, patch_pymongo_database, patch_salt_dict:
        ret = mongodb.version()
        assert ret == "6.0.2"


def test_db_list():
    """
    Test mongodb.db_list
    """
    list_db_names_mock = MagicMock(
        autospec=True, return_value=["admin", "config", "local"]
    )
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())

    patch_list_db_names = patch.object(
        MockMongoConnect, "list_database_names", list_db_names_mock
    )
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_list_db_names, patch_mongo_client, patch_pymongo_database, patch_salt_dict:
        ret = mongodb.db_list()
        assert ret == ["admin", "config", "local"]


def test_db_exists():
    """
    Test mongodb.db_exists
    """
    list_db_names_mock = MagicMock(
        autospec=True, return_value=["admin", "config", "local"]
    )
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_list_db_names = patch.object(
        MockMongoConnect, "list_database_names", list_db_names_mock
    )
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_list_db_names, patch_mongo_client, patch_pymongo_database, patch_salt_dict:
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
    database_version = {"version": "6.0.2"}

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    database_command_mock = MagicMock(side_effect=[database_version, user_info])
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", database_command_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_pymongo_command, patch_salt_dict:
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
    database_version = {"version": "6.0.2"}

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)

    with patch_mongo_client, patch_pymongo_database:
        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        database_command_mock = MagicMock(
            autospec=True, side_effect=[database_version, user_info]
        )

        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )
        patch_pymongo_command = patch.object(
            MockPyMongoDatabase, "command", database_command_mock
        )

        with patch_salt_dict, patch_pymongo_command:
            ret = mongodb.user_exists("test_user")
            assert ret

        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        database_command_mock = MagicMock(
            autospec=True, side_effect=[database_version, user_info]
        )

        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )
        patch_pymongo_command = patch.object(
            MockPyMongoDatabase, "command", database_command_mock
        )

        with patch_salt_dict, patch_pymongo_command:
            ret = mongodb.user_exists("no_test_user")
            assert not ret


def test_user_create():
    """
    Test mongodb.user_create
    """
    user_create_mock = MagicMock(return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_create_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_create("test_user", "test_password")
        assert ret


def test_user_create_exception():
    """
    Test mongodb.user_create
    """
    user_create_mock = MagicMock(side_effect=pymongo.errors.PyMongoError)

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_create_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_create("test_user", "test_password")
        assert not ret


def test_user_remove():
    """
    Test mongodb.user_remove
    """
    user_remove_mock = MagicMock(autospec=True, return_value={"ok": 1.0})

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_remove_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_remove("test_user")
        assert ret


def test_user_remove_exception():
    """
    Test mongodb.user_remove
    """
    user_remove_mock = MagicMock(autospec=True, side_effect=pymongo.errors.PyMongoError)

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_remove_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_remove("test_user")
        assert not ret


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
    database_version = {"version": "6.0.2"}

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )
    database_command_mock = MagicMock(
        autospec=True, side_effect=[database_version, user_info]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", database_command_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_roles_exists("test_user", '["read"]', "admin")
        assert ret


def test_user_grant_roles():
    """
    Test mongodb.user_remove
    """
    user_grant_roles_mock = MagicMock(autospec=True, return_value={"ok": 1.0})
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_grant_roles_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_grant_roles(
            "test_user", '[{"role": "readWrite", "db": "admin" }]', "admin"
        )
        assert ret


def test_user_revoke_roles():
    """
    Test mongodb.user_remove
    """
    user_revoke_roles_mock = MagicMock(autospec=True, return_value={"ok": 1.0})
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", user_revoke_roles_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.user_revoke_roles(
            "test_user", '[{"role": "readWrite", "db": "admin" }]', "admin"
        )
        assert ret


def test_collection_create():
    """
    Test mongodb.user_create
    """
    collection_create_mock = MagicMock(autospec=True, return_value={"ok": 1.0})
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_command = patch.object(
        MockPyMongoDatabase, "command", collection_create_mock
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_command:
        ret = mongodb.collection_create("test_collection")
        assert ret


def test_collections_list():
    """
    Test mongodb.collections_list
    """
    collections_list = MagicMock(
        autospec=True, return_value=["system.users", "mycollection", "system.version"]
    )
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )

    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_list_collection_names = patch.object(
        MockPyMongoDatabase, "list_collection_names", collections_list
    )
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )

    with patch_mongo_client, patch_pymongo_database, patch_salt_dict, patch_pymongo_list_collection_names:
        ret = mongodb.collections_list()
        assert ret == ["system.users", "mycollection", "system.version"]


def test_insert():
    """
    Test mongodb.insert
    """
    collection_insert_mock = MockInsertResult()

    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    config_option_mock = MagicMock(
        autospec=True, side_effect=["user", "password", "localhost", "27017"]
    )
    pymongo_collection_mock = MagicMock(
        autospec=True, return_value=MockPyMongoCollection()
    )

    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_salt_dict = patch.dict(
        mongodb.__salt__, {"config.option": config_option_mock}
    )
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_pymongo_collection = patch.object(mongodb, "getattr", pymongo_collection_mock)

    with patch_mongo_client, patch_salt_dict, patch_pymongo_database, patch_pymongo_collection:
        patch_pymongo_collection_insert = patch.object(
            MockPyMongoCollection,
            "insert_many",
            MagicMock(return_value=collection_insert_mock),
        )
        with patch_pymongo_collection_insert:
            ret = mongodb.insert(
                '[{"foo": "FOO", "bar": "BAR"}, {"foo": "BAZ", "bar": "BAM"}]',
                "my_collection",
            )
            assert ret


def test_find():
    """
    Test mongodb.find
    """
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    pymongo_collection_mock = MagicMock(
        autospec=True, return_value=MockPyMongoCollection()
    )

    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_pymongo_collection = patch.object(mongodb, "getattr", pymongo_collection_mock)

    with patch_mongo_client, patch_pymongo_database, patch_pymongo_collection:
        collection_find_mock = [
            {"_id": "63459d7f78548d1d02295dd0", "foo": "FOO", "bar": "BAR"},
            {"_id": "6345c4fea9a1255a430b2fef", "foo": "FOO", "bar": "BAR"},
            {"_id": "6345c505961560271e34a22a", "foo": "FOO", "bar": "BAR"},
        ]

        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )
        patch_pymongo_collection_find = patch.object(
            MockPyMongoCollection, "find", MagicMock(return_value=collection_find_mock)
        )
        with patch_pymongo_collection_find, patch_salt_dict:
            expected = [
                {"_id": "63459d7f78548d1d02295dd0", "foo": "FOO", "bar": "BAR"},
                {"_id": "6345c4fea9a1255a430b2fef", "foo": "FOO", "bar": "BAR"},
                {"_id": "6345c505961560271e34a22a", "foo": "FOO", "bar": "BAR"},
                {"_id": "63459d7f78548d1d02295dd0", "foo": "FOO", "bar": "BAR"},
                {"_id": "6345c4fea9a1255a430b2fef", "foo": "FOO", "bar": "BAR"},
                {"_id": "6345c505961560271e34a22a", "foo": "FOO", "bar": "BAR"},
            ]
            ret = mongodb.find(
                "test_collection",
                ['{"foo": "FOO", "bar": "BAR"}', '{"foo": "BAZ", "bar": "BAM"}'],
            )
            assert ret == expected

        collection_find_mock = [{"_id": "63459d7f78548d1d02295dd0", "baz": "BAZ"}]

        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )
        patch_pymongo_collection_find = patch.object(
            MockPyMongoCollection, "find", MagicMock(return_value=collection_find_mock)
        )
        with patch_pymongo_collection_find, patch_salt_dict:
            expected = [{"_id": "63459d7f78548d1d02295dd0", "baz": "BAZ"}]
            ret = mongodb.find("my_collection", {"baz": "BAZ"})
            assert ret == expected


def test_remove():
    """
    Test mongodb.remove
    """
    mongodb_client_mock = MagicMock(autospec=True, return_value=MockMongoConnect())
    pymongo_database_mock = MagicMock(autospec=True, return_value=MockPyMongoDatabase())
    pymongo_collection_mock = MagicMock(
        autospec=True, return_value=MockPyMongoCollection()
    )

    patch_mongo_client = patch("pymongo.MongoClient", mongodb_client_mock)
    patch_pymongo_database = patch("pymongo.database.Database", pymongo_database_mock)
    patch_pymongo_collection = patch.object(mongodb, "getattr", pymongo_collection_mock)

    with patch_mongo_client, patch_pymongo_database, patch_pymongo_collection:
        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )

        # Assume we delete one entry each time
        collection_delete_one_mock = MockDeleteResult()
        collection_delete_one_mock.deleted_count = 1
        collection_delete_one_mock.raw_result = {"n": 1, "ok": 1.0}
        collection_delete_one_mock.acknowledged = True

        patch_pymongo_collection_remove = patch.object(
            MockPyMongoCollection,
            "delete_one",
            MagicMock(return_value=collection_delete_one_mock),
        )
        with patch_pymongo_collection_remove, patch_salt_dict:

            ret = mongodb.remove(
                "test_collection",
                ['{"foo": "FOO", "bar": "BAR"}', '{"foo": "BAZ", "bar": "BAM"}'],
            )
            expected = "2 objects removed"
            assert ret == expected

        config_option_mock = MagicMock(
            autospec=True, side_effect=["user", "password", "localhost", "27017"]
        )
        patch_salt_dict = patch.dict(
            mongodb.__salt__, {"config.option": config_option_mock}
        )

        # Assume we delete one entry each time
        collection_delete_one_mock = MockDeleteResult()
        collection_delete_one_mock.deleted_count = 1
        collection_delete_one_mock.raw_result = {"n": 1, "ok": 1.0}
        collection_delete_one_mock.acknowledged = True

        patch_pymongo_collection_remove = patch.object(
            MockPyMongoCollection,
            "delete_one",
            MagicMock(return_value=collection_delete_one_mock),
        )
        with patch_pymongo_collection_remove, patch_salt_dict:

            ret = mongodb.remove("test_collection", {"foo": "FOO", "bar": "BAR"})
            expected = "1 objects removed"
            assert ret == expected
