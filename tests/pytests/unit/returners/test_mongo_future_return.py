import pytest

import salt.exceptions
import salt.returners.mongo_future_return as mongo
from salt.utils.versions import Version
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():

    return {
        mongo: {
            "__opts__": {
                "mongo.uri": "mongodb://root:pass@localhost27017/salt?authSource=admin"
            }
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
    ), patch.dict(mongo.__opts__, opts):
        with pytest.raises(salt.exceptions.SaltConfigurationError):
            mongo.returner({})
