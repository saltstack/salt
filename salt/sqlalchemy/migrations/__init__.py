"""
Alembic schema migrations for the SQLAlchemy cache and returner.

Migrations run only through the ``sqlalchemy`` runner, never at daemon
startup. Online runs hold a database lock so concurrent masters cannot
apply the same revision twice.
"""

import contextlib
import io
import os

import salt.exceptions
import salt.sqlalchemy

try:
    import alembic.command
    import alembic.config
    import alembic.runtime.migration
    import alembic.script
    import sqlalchemy

    HAS_ALEMBIC = True
except ImportError:
    HAS_ALEMBIC = False

SETTINGS_TABLE = "salt_schema_settings"
LOCK_NAME = "salt_sqlalchemy_migrations"
LOCK_TIMEOUT = 600

# Settings that decide table structure. Changing one later needs a manual
# migration, so upgrades refuse to run against a schema built differently.
STRUCTURAL_SETTINGS = ("partman.enabled",)


def schema_settings(engine_config, dialect_name):
    """
    Return the structural settings recorded when the schema is created.
    """
    # pg_partman only changes table structure on PostgreSQL.
    partman = bool(engine_config["partman.enabled"]) and dialect_name == "postgresql"
    return {"partman.enabled": str(partman).lower()}


def _registry(engine_name):
    if not HAS_ALEMBIC:
        raise salt.exceptions.SaltInvocationError(
            "Alembic must be installed to manage SQLAlchemy schema migrations"
        )
    name = salt.sqlalchemy._engine_name(engine_name)
    try:
        return salt.sqlalchemy.ENGINE_REGISTRY[name]
    except KeyError:
        raise salt.exceptions.SaltInvocationError(
            f"ORM not configured for '{name}' yet. Did you forget to call salt.sqlalchemy.configure_orm?"
        )


def make_config(engine_name=None):
    """
    Build an Alembic configuration for a configured engine, without an ini file.
    """
    registry = _registry(engine_name)
    engine_config = registry["config"]
    config = alembic.config.Config(stdout=io.StringIO(), output_buffer=io.StringIO())
    config.set_main_option("script_location", os.path.dirname(__file__))
    config.attributes.update(
        engine=registry["engine"],
        engine_config=engine_config,
        schema=engine_config.get("schema") or None,
    )
    return config


@contextlib.contextmanager
def migration_lock(connection):
    """
    Hold a session-level database lock for the duration of a migration run.
    """
    dialect = connection.dialect.name
    params = {"name": LOCK_NAME}
    if dialect == "postgresql":
        connection.execute(
            sqlalchemy.text("SELECT pg_advisory_lock(hashtext(:name))"), params
        )
        release = sqlalchemy.text("SELECT pg_advisory_unlock(hashtext(:name))")
    elif dialect in {"mysql", "mariadb"}:
        acquired = connection.scalar(
            sqlalchemy.text("SELECT GET_LOCK(:name, :timeout)"),
            {**params, "timeout": LOCK_TIMEOUT},
        )
        if acquired != 1:
            raise salt.exceptions.SaltException(
                "Timed out waiting for the SQLAlchemy migration lock"
            )
        release = sqlalchemy.text("SELECT RELEASE_LOCK(:name)")
    else:
        # SQLite serializes writers with its own file lock.
        release = None
    # Alembic must start its own transaction, so end the implicit one.
    connection.commit()
    try:
        yield
    finally:
        if release is not None:
            if connection.in_transaction():
                connection.rollback()
            connection.execute(release, params)
            connection.commit()


def _recorded_settings(engine, schema):
    if not sqlalchemy.inspect(engine).has_table(SETTINGS_TABLE, schema=schema):
        return {}
    table = sqlalchemy.Table(
        SETTINGS_TABLE, sqlalchemy.MetaData(), autoload_with=engine, schema=schema
    )
    with engine.connect() as connection:
        return dict(
            connection.execute(sqlalchemy.select(table.c.name, table.c.value)).all()
        )


def check_settings(config):
    """
    Refuse upgrades when structural settings differ from the existing schema.
    """
    attributes = config.attributes
    engine = attributes["engine"]
    recorded = _recorded_settings(engine, attributes["schema"])
    expected = schema_settings(attributes["engine_config"], engine.dialect.name)
    changed = sorted(
        name
        for name in STRUCTURAL_SETTINGS
        if name in recorded and recorded[name] != expected[name]
    )
    if changed:
        details = ", ".join(
            f"sqlalchemy.{name} is {expected[name]} but the schema was created with {recorded[name]}"
            for name in changed
        )
        raise salt.exceptions.SaltConfigurationError(
            f"Existing SQLAlchemy schema does not match the configuration: {details}. "
            "Changing these settings requires a manual data migration."
        )


def upgrade(revision="head", engine_name=None, sql=False):
    """
    Upgrade the schema. With ``sql``, return the SQL instead of running it.
    """
    config = make_config(engine_name)
    if not sql:
        check_settings(config)
    alembic.command.upgrade(config, revision, sql=sql)
    return config.output_buffer.getvalue() if sql else current(engine_name)


def downgrade(revision, engine_name=None, sql=False):
    """
    Downgrade the schema. With ``sql``, return the SQL instead of running it.
    """
    config = make_config(engine_name)
    alembic.command.downgrade(config, revision, sql=sql)
    return config.output_buffer.getvalue() if sql else current(engine_name)


def stamp(revision, engine_name=None):
    """
    Record a revision as applied without running its migrations.
    """
    config = make_config(engine_name)
    alembic.command.stamp(config, revision)
    return current(engine_name)


def current(engine_name=None):
    """
    Return the revisions currently applied to the database.
    """
    config = make_config(engine_name)
    with config.attributes["engine"].connect() as connection:
        context = alembic.runtime.migration.MigrationContext.configure(
            connection, opts={"version_table_schema": config.attributes["schema"]}
        )
        return sorted(context.get_current_heads())


def history(engine_name=None):
    """
    Return the available revisions, newest first.
    """
    script = alembic.script.ScriptDirectory.from_config(make_config(engine_name))
    return [
        {
            "revision": rev.revision,
            "down_revision": rev.down_revision,
            "description": rev.doc,
        }
        for rev in script.walk_revisions()
    ]
