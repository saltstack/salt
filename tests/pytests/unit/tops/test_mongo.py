import pytest

import salt.tops.mongo
from tests.support.mock import patch


@pytest.mark.parametrize(
    "expected_ssl, use_ssl",
    [
        (True, {"mongo.ssl": True}),
        (False, {"mongo.ssl": False}),
        (False, {"mongo.ssl": None}),
        (False, {}),
    ],
)
def test_tops_should_correctly_pass_ssl_arg_to_MongoClient(expected_ssl, use_ssl):
    salt.tops.mongo.HAS_PYMONGO = True
    with patch("salt.tops.mongo.pymongo", create=True) as fake_pymongo, patch.dict(
        "salt.tops.mongo.__opts__",
        {
            **use_ssl,
            **{
                "master_tops": {"mongo": {}},
                "mongo.host": "fnord",
                "mongo.port": "fnord",
            },
        },
    ):
        salt.tops.mongo.top(opts={"id": "fnord"})
        fake_pymongo.MongoClient.assert_called_with(
            host="fnord", port="fnord", ssl=expected_ssl
        )


def test_tops_should_pass_auth_to_MongoClient_for_pymongo_v4():
    """
    Test that authentication credentials are passed to MongoClient constructor
    for pymongo v4 compatibility, not using deprecated mdb.authenticate()
    """
    salt.tops.mongo.HAS_PYMONGO = True
    with patch("salt.tops.mongo.pymongo", create=True) as fake_pymongo, patch.dict(
        "salt.tops.mongo.__opts__",
        {
            "master_tops": {"mongo": {}},
            "mongo.host": "localhost",
            "mongo.port": 27017,
            "mongo.user": "testuser",
            "mongo.password": "testpass",
            "mongo.db": "salt",
        },
    ):
        salt.tops.mongo.top(opts={"id": "test-minion"})

        # Verify MongoClient is called with authentication parameters
        fake_pymongo.MongoClient.assert_called_with(
            host="localhost",
            port=27017,
            ssl=False,
            username="testuser",
            password="testpass",
            authSource="admin",
        )

        # Verify that authenticate() is NOT called (pymongo v4 compatibility)
        fake_db = fake_pymongo.MongoClient.return_value.__getitem__.return_value
        assert not fake_db.authenticate.called


def test_tops_should_use_custom_authdb():
    """
    Test that custom authdb is passed correctly to MongoClient
    """
    salt.tops.mongo.HAS_PYMONGO = True
    with patch("salt.tops.mongo.pymongo", create=True) as fake_pymongo, patch.dict(
        "salt.tops.mongo.__opts__",
        {
            "master_tops": {"mongo": {}},
            "mongo.host": "localhost",
            "mongo.port": 27017,
            "mongo.user": "testuser",
            "mongo.password": "testpass",
            "mongo.authdb": "myauthdb",
            "mongo.db": "salt",
        },
    ):
        salt.tops.mongo.top(opts={"id": "test-minion"})

        # Verify custom authSource is used
        fake_pymongo.MongoClient.assert_called_with(
            host="localhost",
            port=27017,
            ssl=False,
            username="testuser",
            password="testpass",
            authSource="myauthdb",
        )


def test_tops_without_auth_should_not_pass_credentials():
    """
    Test that when no credentials are provided, MongoClient is called without auth params
    """
    salt.tops.mongo.HAS_PYMONGO = True
    with patch("salt.tops.mongo.pymongo", create=True) as fake_pymongo, patch.dict(
        "salt.tops.mongo.__opts__",
        {
            "master_tops": {"mongo": {}},
            "mongo.host": "localhost",
            "mongo.port": 27017,
            "mongo.db": "salt",
        },
    ):
        salt.tops.mongo.top(opts={"id": "test-minion"})

        # Verify MongoClient is called without authentication parameters
        fake_pymongo.MongoClient.assert_called_with(
            host="localhost",
            port=27017,
            ssl=False,
        )
