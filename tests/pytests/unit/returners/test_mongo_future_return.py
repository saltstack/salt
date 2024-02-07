import pytest

import salt.exceptions
import salt.returners.mongo_future_return as mongo_future_return
from salt.utils.versions import Version
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    fake_opts = {"mongo.host": "fnord", "mongo.port": "fnordport"}
    return {
        mongo_future_return: {
            "__opts__": fake_opts,
            "__salt__": {"config.option": fake_opts.get},
        }
    }


def test_config_exception():
    opts = {
        "mongo.host": "localhost",
        "mongo.port": 27017,
        "mongo.user": "root",
        "mongo.password": "pass",
        "mongo.uri": "mongodb://root:pass@localhost27017/salt?authSource=admin",
    }
    with patch(
        "salt.returners.mongo_future_return.PYMONGO_VERSION",
        Version("4.3.2"),
        create=True,
    ), patch.dict(mongo_future_return.__opts__, opts):
        with pytest.raises(salt.exceptions.SaltConfigurationError):
            mongo_future_return.returner({})


@pytest.mark.parametrize(
    "expected_ssl, use_ssl",
    [
        (True, {"fnord.mongo.ssl": True}),
        (False, {"fnord.mongo.ssl": False}),
        (False, {"fnord.mongo.ssl": None}),
        (False, {}),
    ],
)
def test_mongo_future_returner_should_correctly_pass_ssl_to_MongoClient_when_ret_is_set(
    expected_ssl, use_ssl
):
    with patch(
        "salt.returners.mongo_future_return.pymongo", create=True
    ) as fake_mongo, patch.object(
        mongo_future_return,
        "PYMONGO_VERSION",
        mongo_future_return.Version("99999"),
        create=True,
    ), patch.dict(
        "salt.returners.mongo_future_return.__opts__",
        {
            **use_ssl,
            **{"fnord.mongo.host": "fnordfnord", "fnord.mongo.port": "fnordfnordport"},
        },
    ):
        mongo_future_return._get_conn(ret={"ret_config": "fnord"})
        fake_mongo.MongoClient.assert_called_with(
            "fnordfnord",
            "fnordfnordport",
            username=None,
            password=None,
            ssl=expected_ssl,
        )


@pytest.mark.parametrize(
    "expected_ssl, use_ssl",
    [
        (True, {"mongo.ssl": True}),
        (False, {"mongo.ssl": False}),
        (False, {"mongo.ssl": None}),
        (False, {}),
    ],
)
def test_mongo_future_returner_should_correctly_pass_ssl_to_MongoClient(
    expected_ssl, use_ssl
):
    # Here these fnord.X.Y config options should be ignored
    with patch(
        "salt.returners.mongo_future_return.pymongo", create=True
    ) as fake_mongo, patch.object(
        mongo_future_return,
        "PYMONGO_VERSION",
        mongo_future_return.Version("99999"),
        create=True,
    ), patch.dict(
        "salt.returners.mongo_future_return.__opts__",
        {
            **use_ssl,
            **{"fnord.mongo.host": "fnordfnord", "fnord.mongo.port": "fnordfnordport"},
        },
    ):
        mongo_future_return._get_conn(ret=None)
        fake_mongo.MongoClient.assert_called_with(
            "fnord", "fnordport", username=None, password=None, ssl=expected_ssl
        )
