"""Create the SQLAlchemy cache and job tables.

Revision ID: 0001
Revises:
"""

import types

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects.mysql import TEXT as MySQL_TEXT

import salt.exceptions
import salt.sqlalchemy.migrations
from salt.sqlalchemy.models import (
    DateTimeUTC,
    _create_partman_parent,
    _drop_partman_parent,
    get_json_type,
    get_text_type,
    jid_timestamp,
    utcnow,
)

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Frozen here so later model changes cannot alter this revision.
CACHE_PARTITIONS = {
    "default": None,
    "keys": "'keys', 'denied_keys', 'master_keys'",
    "grains": "'grains'",
    "pillar": "'pillar'",
    "tokens": "'tokens'",
    "mine": "'mine'",
}
PARTMAN_TABLES = ("events", "jids", "jid_minions", "returns")


def _gin_index(table, column, schema):
    op.create_index(
        f"ix_{table}_{column}",
        table,
        [column],
        schema=schema,
        postgresql_using="gin",
        postgresql_with={"FASTUPDATE": "OFF"},
    )


def _jid_check(table):
    jid = sa.column("jid")
    return sa.CheckConstraint(
        (sa.column("created_at") == jid_timestamp(jid))
        & jid_timestamp(jid).is_not(None),
        name=f"{table}_timestamp_matches_jid",
    )


def _qualified(preparer, schema, name):
    prefix = f"{preparer.quote_schema(schema)}." if schema else ""
    return prefix + preparer.quote(name)


def upgrade():
    attributes = context.config.attributes
    engine_config = attributes["engine_config"]
    schema = attributes["schema"]
    dialect = op.get_context().dialect
    is_postgres = dialect.name == "postgresql"
    partman = is_postgres and engine_config["partman.enabled"]
    if partman and context.is_offline_mode():
        raise salt.exceptions.SaltConfigurationError(
            "Offline SQL generation does not support pg_partman. "
            "Run the upgrade against the database instead."
        )

    # The type helpers only need the dialect.
    bind = types.SimpleNamespace(dialect=dialect)
    text_type = get_text_type(bind)
    json_type = get_json_type(bind)
    range_partitioned = {"postgresql_partition_by": "RANGE (created_at)"}
    partition_args = range_partitioned if partman else {}

    cache = op.create_table(
        "cache",
        sa.Column("bank", text_type, primary_key=True),
        sa.Column("key", text_type, primary_key=True),
        sa.Column("data", json_type, nullable=False),
        sa.Column("cluster", text_type, primary_key=True),
        sa.Column(
            "created_at", DateTimeUTC(6), server_default=utcnow(), nullable=False
        ),
        sa.Column("expires_at", DateTimeUTC(), nullable=True),
        schema=schema,
        postgresql_partition_by="LIST (bank)",
    )
    op.create_index("ix_cache_bank", "cache", ["bank"], schema=schema)
    op.create_index("ix_cache_key", "cache", ["key"], schema=schema)
    if is_postgres:
        _gin_index("cache", "data", schema)
        preparer = dialect.identifier_preparer
        parent = _qualified(preparer, schema, cache.name)
        for suffix, values in CACHE_PARTITIONS.items():
            child = _qualified(preparer, schema, f"{cache.name}_{suffix}")
            bounds = "DEFAULT" if values is None else f"FOR VALUES IN ({values})"
            op.execute(
                f"CREATE TABLE IF NOT EXISTS {child} PARTITION OF {parent} {bounds}"
            )

    tables = {}
    tables["events"] = op.create_table(
        "events",
        sa.Column("tag", text_type, nullable=False),
        sa.Column("data", json_type, nullable=False),
        sa.Column("master_id", text_type, nullable=False),
        sa.Column("cluster", text_type, nullable=False),
        sa.Column("created_at", DateTimeUTC(), server_default=utcnow(), nullable=False),
        schema=schema,
        **partition_args,
    )
    op.create_index("ix_events_tag", "events", ["tag"], schema=schema)
    op.create_index("ix_events_created_at", "events", ["created_at"], schema=schema)
    if is_postgres:
        _gin_index("events", "data", schema)

    tables["jids"] = op.create_table(
        "jids",
        sa.Column("jid", text_type, primary_key=True),
        sa.Column("load", json_type, nullable=False),
        sa.Column("minions", json_type, nullable=True),
        sa.Column("cluster", text_type, primary_key=True),
        sa.Column("created_at", DateTimeUTC(), primary_key=True),
        _jid_check("jids"),
        schema=schema,
        **partition_args,
    )
    op.create_index("ix_jids_created_at", "jids", ["created_at"], schema=schema)
    if is_postgres:
        _gin_index("jids", "load", schema)

    tables["jid_minions"] = op.create_table(
        "jid_minions",
        sa.Column("jid", text_type, primary_key=True),
        sa.Column("cluster", text_type, primary_key=True),
        sa.Column("created_at", DateTimeUTC(), primary_key=True),
        sa.Column("minion_id", text_type, primary_key=True),
        _jid_check("jid_minions"),
        schema=schema,
        **partition_args,
    )
    op.create_index(
        "ix_jid_minions_created_at", "jid_minions", ["created_at"], schema=schema
    )

    tables["returns"] = op.create_table(
        "returns",
        sa.Column(
            "fun",
            sa.Text().with_variant(
                MySQL_TEXT(charset="utf8mb4", collation="utf8mb4_bin"),
                "mysql",
                "mariadb",
            ),
            nullable=False,
        ),
        sa.Column("jid", text_type, nullable=False),
        sa.Column("id", text_type, nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ret", json_type, nullable=False),
        sa.Column("cluster", text_type, nullable=False),
        sa.Column("created_at", DateTimeUTC(), server_default=utcnow(), nullable=False),
        schema=schema,
        **partition_args,
    )
    op.create_index(
        "ix_returns_fun",
        "returns",
        ["fun"],
        schema=schema,
        mysql_length=255,
        mariadb_length=255,
    )
    op.create_index("ix_returns_jid", "returns", ["jid"], schema=schema)
    op.create_index("ix_returns_id", "returns", ["id"], schema=schema)
    op.create_index("ix_returns_created_at", "returns", ["created_at"], schema=schema)
    if is_postgres:
        _gin_index("returns", "ret", schema)

    if partman:
        for name in PARTMAN_TABLES:
            _create_partman_parent(tables[name], op.get_bind(), engine_config)

    settings = op.create_table(
        salt.sqlalchemy.migrations.SETTINGS_TABLE,
        sa.Column("name", sa.String(255), primary_key=True),
        sa.Column("value", sa.String(255), nullable=False),
        schema=schema,
    )
    op.bulk_insert(
        settings,
        [
            {"name": name, "value": value}
            for name, value in salt.sqlalchemy.migrations.schema_settings(
                engine_config, dialect.name
            ).items()
        ],
    )


def downgrade():
    attributes = context.config.attributes
    engine_config = attributes["engine_config"]
    schema = attributes["schema"]
    partman = (
        op.get_context().dialect.name == "postgresql"
        and engine_config["partman.enabled"]
    )
    if partman and context.is_offline_mode():
        raise salt.exceptions.SaltConfigurationError(
            "Offline SQL generation does not support pg_partman. "
            "Run the downgrade against the database instead."
        )

    for name in ("jid_minions", "returns", "jids", "events", "cache"):
        op.drop_table(name, schema=schema)
        if partman and name in PARTMAN_TABLES:
            _drop_partman_parent(
                sa.table(name, schema=schema), op.get_bind(), engine_config
            )
    op.drop_table(salt.sqlalchemy.migrations.SETTINGS_TABLE, schema=schema)
