"""Add searchable terms to cached grains and pillar.

Revision ID: 0002
Revises: 0001
"""

import logging

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from salt.sqlalchemy import terms

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# Frozen here so later changes to terms.BANKS cannot alter this revision.
BANKS = ("grains", "pillar")
BATCH = 1000


def upgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    schema = context.config.attributes["schema"]
    op.add_column("cache", sa.Column("terms", ARRAY(sa.Text)), schema=schema)
    op.add_column("cache", sa.Column("terms_config", sa.Text), schema=schema)
    preparer = op.get_context().dialect.identifier_preparer
    for statement in terms.index_statements(
        preparer, schema, BANKS
    ) + terms.trigger_statements(preparer, schema, BANKS):
        op.execute(statement)
    if context.is_offline_mode():
        # Rows without terms are rechecked until a master stores them again.
        log.warning("Offline SQL does not compute terms for existing cache rows")
        return
    _backfill(schema, terms.paths(context.config.attributes["engine_config"]))


def _backfill(schema, paths):
    """Compute terms for existing rows with the Python flattener."""
    cache = sa.table(
        "cache",
        sa.column("bank", sa.Text),
        sa.column("key", sa.Text),
        sa.column("cluster", sa.Text),
        sa.column("data", JSONB),
        sa.column("terms", ARRAY(sa.Text)),
        sa.column("terms_config", sa.Text),
        schema=schema,
    )
    bind = op.get_bind()
    for bank in BANKS:
        last = ("", "")
        while True:
            # Walk the primary key in batches rather than holding a cursor.
            rows = bind.execute(
                sa.select(cache.c.cluster, cache.c.key, cache.c.data)
                .where(
                    cache.c.bank == bank,
                    sa.tuple_(cache.c.cluster, cache.c.key) > last,
                )
                .order_by(cache.c.cluster, cache.c.key)
                .limit(BATCH)
            ).all()
            if not rows:
                break
            bind.execute(
                sa.update(cache)
                .where(
                    cache.c.bank == bank,
                    cache.c.cluster == sa.bindparam("b_cluster"),
                    cache.c.key == sa.bindparam("b_key"),
                )
                .values(terms=sa.bindparam("b_terms"), terms_config=paths.fingerprint),
                [
                    {
                        "b_cluster": cluster,
                        "b_key": key,
                        "b_terms": terms.flatten(data, paths),
                    }
                    for cluster, key, data in rows
                ],
            )
            last = (rows[-1].cluster, rows[-1].key)


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
