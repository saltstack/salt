import logging

import pytest

import salt.cache
from tests.pytests.functional.cache.helpers import run_common_cache_tests
from tests.support.pytest.database import (  # pylint: disable=unused-import
    available_databases,
    database_backend,
)

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.parametrize(
        "database_backend",
        available_databases(
            [
                ("mysql-server", "5.5"),
                ("mysql-server", "5.6"),
                ("mysql-server", "5.7"),
                ("mysql-server", "8.0"),
                ("mariadb", "10.3"),
                ("mariadb", "10.4"),
                ("mariadb", "10.5"),
                ("percona", "5.6"),
                ("percona", "5.7"),
                ("percona", "8.0"),
            ]
        ),
        indirect=True,
    ),
]


@pytest.fixture
def cache(minion_opts, database_backend):
    opts = minion_opts.copy()
    opts["cache"] = "mysql"
    opts["mysql.host"] = "127.0.0.1"
    opts["mysql.port"] = database_backend.port
    opts["mysql.user"] = database_backend.user
    opts["mysql.password"] = database_backend.passwd
    opts["mysql.database"] = database_backend.database
    opts["mysql.table_name"] = "cache"
    cache = salt.cache.factory(opts)
    return cache


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)
