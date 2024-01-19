import pytest

import salt.returners.mongo_return as mongo_return
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    fake_opts = {"mongo.host": "fnord", "mongo.port": "fnordport"}
    return {
        mongo_return: {
            "__opts__": fake_opts,
            "__salt__": {"config.option": fake_opts.get},
        }
    }


@pytest.mark.parametrize(
    "expected_ssl, use_ssl",
    [
        (True, {"fnord.mongo.ssl": True}),
        (False, {"fnord.mongo.ssl": False}),
        (False, {"fnord.mongo.ssl": None}),
        (False, {}),
    ],
)
def test_mongo_returner_should_correctly_pass_ssl_to_MongoClient_when_ret_is_set(
    expected_ssl, use_ssl
):
    with patch(
        "salt.returners.mongo_return.pymongo", create=True
    ) as fake_mongo, patch.object(
        mongo_return,
        "PYMONGO_VERSION",
        mongo_return.Version("99999"),
        create=True,
    ), patch.dict(
        "salt.returners.mongo_return.__opts__",
        {
            **use_ssl,
            **{"fnord.mongo.host": "fnordfnord", "fnord.mongo.port": "fnordfnordport"},
        },
    ):
        mongo_return._get_conn(ret={"ret_config": "fnord"})
        fake_mongo.MongoClient.assert_called_with(
            host="fnordfnord", port="fnordfnordport", ssl=expected_ssl
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
def test_mongo_returner_should_correctly_pass_ssl_to_MongoClient(expected_ssl, use_ssl):
    # Here these fnord.X.Y config options should be ignored
    with patch(
        "salt.returners.mongo_return.pymongo", create=True
    ) as fake_mongo, patch.object(
        mongo_return,
        "PYMONGO_VERSION",
        mongo_return.Version("99999"),
        create=True,
    ), patch.dict(
        "salt.returners.mongo_return.__opts__",
        {
            **use_ssl,
            **{"fnord.mongo.host": "fnordfnord", "fnord.mongo.port": "fnordfnordport"},
        },
    ):
        mongo_return._get_conn(ret=None)
        fake_mongo.MongoClient.assert_called_with(
            host="fnord", port="fnordport", ssl=expected_ssl
        )
