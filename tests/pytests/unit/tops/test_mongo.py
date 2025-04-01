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
