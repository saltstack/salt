"""Add searchable terms to cached grains and pillar.

Revision ID: 0002
Revises: 0001
"""

import logging

import sqlalchemy as sa
from alembic import context, op

from salt.sqlalchemy import terms

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# Frozen here so later changes to terms.BANKS cannot alter this revision.
BANKS = ("grains", "pillar")


def upgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    schema = context.config.attributes["schema"]
    preparer = op.get_context().dialect.identifier_preparer
    cache = f"{preparer.quote_schema(schema)}.cache" if schema else "cache"
    # The batches and index builds below commit before the revision is
    # recorded, so an interrupted upgrade reruns this revision from the start;
    # every step here tolerates that.
    op.execute(f"ALTER TABLE {cache} ADD COLUMN IF NOT EXISTS terms text[]")
    op.execute(f"ALTER TABLE {cache} ADD COLUMN IF NOT EXISTS terms_config text")
    for statement in terms.trigger_statements(preparer, schema, BANKS):
        op.execute(statement)
    # Batches and concurrent index builds commit on their own, so a large
    # cache stays writable and is not rewritten in one transaction.
    with op.get_context().autocommit_block():
        if context.is_offline_mode():
            # Rows without terms are rechecked until they are rebuilt.
            log.warning(
                "Offline SQL does not compute terms for existing cache rows; "
                "run salt-run sqlalchemy.rebuild_terms afterwards"
            )
        else:
            # Computing terms before indexing avoids index maintenance per row.
            paths = terms.paths(context.config.attributes["engine_config"])
            terms.rebuild(op.get_bind(), schema, paths, BANKS)
            _drop_invalid_indexes(schema)
        for statement in terms.index_statements(
            preparer, schema, BANKS, concurrently=True
        ):
            op.execute(statement)


def _drop_invalid_indexes(schema):
    """Drop indexes an interrupted concurrent build left invalid."""
    preparer = op.get_context().dialect.identifier_preparer
    names = [
        f"ix_cache_{bank}_{suffix}"
        for bank in BANKS
        for suffix in ("terms", "terms_config")
    ]
    invalid = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT c.relname FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indexrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE NOT i.indisvalid AND c.relname = ANY(:names) "
                "AND n.nspname = coalesce(:schema, current_schema())"
            ),
            {"names": names, "schema": schema},
        )
        .scalars()
    )
    for name in invalid:
        prefix = f"{preparer.quote_schema(schema)}." if schema else ""
        op.execute(f"DROP INDEX CONCURRENTLY {prefix}{preparer.quote(name)}")


def downgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    schema = context.config.attributes["schema"]
    preparer = op.get_context().dialect.identifier_preparer
    # The trigger function refers to the columns by name.
    for statement in terms.drop_trigger_statements(preparer, schema, BANKS):
        op.execute(statement)
    op.drop_column("cache", "terms_config", schema=schema)
    op.drop_column("cache", "terms", schema=schema)
