import pytest

import salt.exceptions
import salt.pillar.mongo as mongo
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {mongo: {"__opts__": {}}}


def test_config_exception():
    opts = {
        "mongo.host": "localhost",
        "mongo.port": 27017,
        "mongo.user": "root",
        "mongo.password": "pass",
        "mongo.db": "admin",
        "mongo.uri": "mongodb://root:pass@localhost27017/salt?authSource=admin",
    }
    with patch.dict(mongo.__opts__, opts):
        with pytest.raises(salt.exceptions.SaltConfigurationError):
            mongo.ext_pillar("minion1", {})


@pytest.mark.parametrize(
    "expected_ssl, use_ssl",
    [
        (True, {"mongo.ssl": True}),
        (False, {"mongo.ssl": False}),
        (False, {"mongo.ssl": None}),
        (False, {}),
    ],
)
def test_mongo_pillar_should_use_ssl_when_set_in_opts(expected_ssl, use_ssl):
    with patch.dict(
        "salt.pillar.mongo.__opts__",
        {**use_ssl, **{"mongo.host": "fnord", "mongo.port": "fnordport"}},
    ), patch("salt.pillar.mongo.pymongo", create=True) as fake_mongo:
        mongo.ext_pillar(minion_id="blarp", pillar=None)
        fake_mongo.MongoClient.assert_called_with(
            host="fnord",
            port="fnordport",
            username=None,
            password=None,
            ssl=expected_ssl,
        )
