"""
Alembic environment for the SQLAlchemy cache and returner.

The runner supplies the configured engine and its settings through
``config.attributes``; there is no ``alembic.ini``.
"""

from alembic import context

import salt.sqlalchemy.migrations

config = context.config
engine = config.attributes["engine"]
schema = config.attributes["schema"]


def run_migrations_offline():
    # Named parameters stop percent signs in literals being doubled.
    context.configure(
        dialect_name=engine.dialect.name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    with engine.connect() as connection, salt.sqlalchemy.migrations.migration_lock(
        connection
    ):
        context.configure(
            connection=connection,
            version_table_schema=schema,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
