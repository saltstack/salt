import os

import pytest

import salt.cache
import salt.sqlalchemy
from tests.pytests.functional.cache.helpers import run_common_cache_tests
from tests.support.pytest.database import available_databases

sqlalchemy = pytest.importorskip("sqlalchemy")

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.parametrize(
        "database_backend",
        available_databases(
            [
                ("mysql-server", "8.0"),
                ("mariadb", "10.4"),
                ("mariadb", "10.5"),
                ("percona", "8.0"),
                ("postgresql", "13"),
                ("postgresql", "17"),
                ("sqlite", None),
            ]
        ),
        indirect=True,
    ),
]


@pytest.fixture
def cache(master_opts, database_backend, tmp_path_factory):
    opts = master_opts.copy()
    opts["cache"] = "sqlalchemy"
    opts["sqlalchemy.echo"] = True

    if database_backend.dialect in {"mysql", "postgresql"}:
        if database_backend.dialect == "mysql":
            driver = "mysql+pymysql"
        elif database_backend.dialect == "postgresql":
            driver = "postgresql+psycopg"

        opts["sqlalchemy.drivername"] = driver
        opts["sqlalchemy.username"] = database_backend.user
        opts["sqlalchemy.password"] = database_backend.passwd
        opts["sqlalchemy.port"] = database_backend.port
        opts["sqlalchemy.database"] = database_backend.database
        opts["sqlalchemy.host"] = "0.0.0.0"
        opts["sqlalchemy.disable_connection_pool"] = True
    elif database_backend.dialect == "sqlite":
        opts["sqlalchemy.dsn"] = "sqlite:///" + os.path.join(
            tmp_path_factory.mktemp("sqlite"), "salt.db"
        )
    else:
        raise ValueError(f"Unsupported returner param: {database_backend}")

    salt.sqlalchemy.reconfigure_orm(opts)
    salt.sqlalchemy.drop_all()
    salt.sqlalchemy.create_all()

    return salt.cache.factory(opts)


@pytest.fixture(scope="module")
def master_opts(
    salt_factories,
    master_id,
    master_config_defaults,
    master_config_overrides,
):
    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=master_config_defaults or None,
        overrides=master_config_overrides,
    )
    return factory.config.copy()


def test_caching(subtests, cache):
    run_common_cache_tests(subtests, cache)
