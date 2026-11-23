import json
import multiprocessing
import os

import pytest

import salt.exceptions
import salt.runners.sqlalchemy
import salt.sqlalchemy
import salt.sqlalchemy.migrations
from salt.sqlalchemy import terms
from tests.support.pytest.database import available_databases, database_backend

__all__ = ["database_backend"]

sqlalchemy = pytest.importorskip("sqlalchemy")
autogenerate = pytest.importorskip("alembic.autogenerate")
alembic_migration = pytest.importorskip("alembic.migration")

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

HEAD = "0002"

TABLES = (
    "jid_minions",
    "returns",
    "jids",
    "events",
    "cache",
    "alembic_version",
    salt.sqlalchemy.migrations.SETTINGS_TABLE,
)


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


@pytest.fixture
def opts(master_opts, database_backend, tmp_path_factory):
    opts = master_opts.copy()
    if database_backend.dialect == "postgresql":
        opts["sqlalchemy.drivername"] = "postgresql+psycopg"
    elif database_backend.dialect == "mysql":
        opts["sqlalchemy.drivername"] = (
            "mariadb+pymysql" if database_backend.name == "mariadb" else "mysql+pymysql"
        )
    elif database_backend.dialect == "sqlite":
        opts["sqlalchemy.dsn"] = "sqlite:///" + os.path.join(
            tmp_path_factory.mktemp("sqlite"), "salt.db"
        )
    else:
        raise ValueError(f"Unsupported database backend: {database_backend}")
    if database_backend.dialect != "sqlite":
        opts["sqlalchemy.username"] = database_backend.user
        opts["sqlalchemy.password"] = database_backend.passwd
        opts["sqlalchemy.port"] = database_backend.port
        opts["sqlalchemy.database"] = database_backend.database
        opts["sqlalchemy.host"] = "0.0.0.0"
        opts["sqlalchemy.disable_connection_pool"] = True
    return opts


def _engine():
    return salt.sqlalchemy.ENGINE_REGISTRY["default"]["engine"]


def _reset(opts, schema=None):
    salt.sqlalchemy.reconfigure_orm(opts)
    engine = _engine()
    preparer = engine.dialect.identifier_preparer
    cascade = " CASCADE" if engine.dialect.name == "postgresql" else ""
    with engine.begin() as connection:
        if schema:
            connection.exec_driver_sql(
                f"CREATE SCHEMA IF NOT EXISTS {preparer.quote_schema(schema)}"
            )
        prefix = f"{preparer.quote_schema(schema)}." if schema else ""
        for table in TABLES:
            connection.exec_driver_sql(
                f"DROP TABLE IF EXISTS {prefix}{preparer.quote(table)}{cascade}"
            )


@pytest.fixture
def configured(opts):
    _reset(opts)
    yield opts
    _reset(opts)


def _schema_diff():
    """Compare the migrated database with the models, ignoring partitions."""

    def include(obj, name, type_, reflected, compare_to):
        if type_ == "table" and reflected and compare_to is None:
            return False
        return True

    Base = salt.sqlalchemy.model_for("Base")
    with _engine().connect() as connection:
        context = alembic_migration.MigrationContext.configure(
            connection, opts={"include_object": include, "compare_type": True}
        )
        return autogenerate.compare_metadata(context, Base.metadata)


def _tables(schema=None):
    return set(sqlalchemy.inspect(_engine()).get_table_names(schema=schema))


def test_upgrade_matches_models(configured):
    assert salt.sqlalchemy.migrations.upgrade() == [HEAD]
    assert _schema_diff() == []
    with _engine().connect() as connection:
        settings = connection.exec_driver_sql(
            f"SELECT name, value FROM {salt.sqlalchemy.migrations.SETTINGS_TABLE}"
        ).all()
    assert dict(settings) == {"partman.enabled": "false"}


def test_upgrade_is_idempotent(configured):
    assert salt.sqlalchemy.migrations.upgrade() == [HEAD]
    assert salt.sqlalchemy.migrations.upgrade() == [HEAD]


def test_downgrade_removes_schema(configured):
    salt.sqlalchemy.migrations.upgrade()
    assert salt.sqlalchemy.migrations.downgrade("base") == []
    assert _tables() & set(TABLES) <= {"alembic_version"}


def test_runner_create_and_drop_all(configured):
    assert salt.runners.sqlalchemy.create_all() is True
    assert salt.runners.sqlalchemy.current() == [HEAD]
    assert {"cache", "jids", "returns"} <= _tables()
    assert salt.runners.sqlalchemy.drop_all() is True
    assert salt.runners.sqlalchemy.current() == []
    assert not _tables() & {"cache", "jids", "returns"}


def test_history_and_stamp(configured):
    history = salt.sqlalchemy.migrations.history()
    assert [revision["revision"] for revision in history] == [HEAD, "0001"]
    assert salt.sqlalchemy.migrations.stamp("head") == [HEAD]
    assert "cache" not in _tables()
    assert salt.sqlalchemy.migrations.stamp("base") == []


def test_offline_sql_does_not_touch_database(configured):
    sql = salt.sqlalchemy.migrations.upgrade(sql=True)
    assert "CREATE TABLE cache" in sql
    assert "INSERT INTO alembic_version" in sql
    dialect = _engine().dialect.name
    if dialect == "postgresql":
        assert "PARTITION OF cache" in sql
    if dialect in {"mysql", "mariadb"}:
        # Named parameters keep the JID CHECK format string intact.
        assert "'%Y%m%d%H%i%s%f'" in sql
        assert "%%Y" not in sql
    assert "DROP TABLE cache" in salt.sqlalchemy.migrations.downgrade(
        "0001:base", sql=True
    )
    assert not _tables() & set(TABLES)


def test_offline_partman_is_refused(configured, database_backend):
    if database_backend.dialect != "postgresql":
        pytest.skip("pg_partman only applies to PostgreSQL")
    _reset({**configured, "sqlalchemy.partman.enabled": True})
    with pytest.raises(salt.exceptions.SaltConfigurationError):
        salt.sqlalchemy.migrations.upgrade(sql=True)


def test_structural_setting_change(configured, database_backend):
    salt.sqlalchemy.migrations.upgrade()
    salt.sqlalchemy.reconfigure_orm({**configured, "sqlalchemy.partman.enabled": True})
    if database_backend.dialect == "postgresql":
        with pytest.raises(
            salt.exceptions.SaltConfigurationError, match="partman.enabled"
        ):
            salt.sqlalchemy.migrations.upgrade()
    else:
        # The setting has no structural effect outside PostgreSQL.
        assert salt.sqlalchemy.migrations.upgrade() == [HEAD]


def test_configured_schema(configured, database_backend):
    if database_backend.dialect != "postgresql":
        pytest.skip("Database schemas are tested on PostgreSQL")
    schema = "salt_migrations"
    opts = {**configured, "sqlalchemy.schema": schema}
    _reset(opts, schema=schema)
    try:
        assert salt.sqlalchemy.migrations.upgrade() == [HEAD]
        tables = _tables(schema)
        assert {"cache", "cache_grains", "jids", "alembic_version"} <= tables
        assert not _tables() & {"cache", "jids", "alembic_version"}
        assert salt.sqlalchemy.migrations.downgrade("base") == []
        assert _tables(schema) & set(TABLES) == {"alembic_version"}
    finally:
        _reset(opts, schema=schema)
        salt.sqlalchemy.reconfigure_orm(configured)


def _upgrade_in_child():
    salt.sqlalchemy.migrations.upgrade()


def test_concurrent_upgrade_waits_for_lock(configured, database_backend):
    if database_backend.dialect == "sqlite":
        pytest.skip("SQLite serializes writers with its own file lock")
    context = multiprocessing.get_context("fork")
    with _engine().connect() as holder:
        with salt.sqlalchemy.migrations.migration_lock(holder):
            child = context.Process(target=_upgrade_in_child)
            child.start()
            child.join(3)
            assert child.is_alive()
            assert salt.sqlalchemy.migrations.current() == []
        child.join(120)
    assert child.exitcode == 0
    assert salt.sqlalchemy.migrations.current() == [HEAD]


def test_terms_backfill(configured, database_backend):
    if database_backend.dialect != "postgresql":
        pytest.skip("Cache terms are PostgreSQL-only")
    salt.sqlalchemy.migrations.upgrade("0001")
    grains = {"os": "Ubuntu", "roles": ["web"]}
    with _engine().begin() as connection:
        connection.execute(
            sqlalchemy.text(
                "INSERT INTO cache (bank, key, cluster, data) VALUES "
                "('grains', 'minion', 'c', CAST(:data AS jsonb)), "
                "('mine', 'minion', 'c', CAST(:data AS jsonb))"
            ),
            {"data": json.dumps(grains)},
        )
    assert salt.sqlalchemy.migrations.upgrade() == [HEAD]
    with _engine().connect() as connection:
        rows = {
            bank: (stored, config)
            for bank, stored, config in connection.exec_driver_sql(
                "SELECT bank, terms, terms_config FROM cache"
            )
        }
        indexes = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'cache_grains'"
            )
        }
    assert rows == {
        "grains": (terms.flatten(grains), terms.ALL.fingerprint),
        "mine": (None, None),
    }
    assert {"ix_cache_grains_terms", "ix_cache_grains_terms_config"} <= indexes
    assert _guard_triggers() == {"cache_grains", "cache_pillar"}
    assert salt.sqlalchemy.migrations.downgrade("0001") == ["0001"]
    with _engine().connect() as connection:
        columns = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'cache'"
            )
        }
    assert "terms" not in columns
    assert _guard_triggers() == set()


def _guard_triggers():
    with _engine().connect() as connection:
        return {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT event_object_table FROM information_schema.triggers "
                f"WHERE trigger_name = '{terms.GUARD}'"
            )
        }
