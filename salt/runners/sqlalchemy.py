"""
Salt runner for managing the SQLAlchemy database schema.

Schema changes are versioned Alembic migrations. Run them explicitly with
this runner; masters never migrate the schema at startup. Migration runners
require the ``alembic`` package.
"""

import logging
from typing import TYPE_CHECKING

import salt.sqlalchemy
import salt.sqlalchemy.migrations
from salt.sqlalchemy import terms

if TYPE_CHECKING:
    __opts__ = {}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if SQLAlchemy ORM can be configured.
    Returns True if successful, False otherwise.
    """
    try:
        salt.sqlalchemy.configure_orm(__opts__)
        return True
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def upgrade(revision="head", target_engine=None, sql=False):
    """
    Upgrade the schema to a revision, ``head`` by default.

    Args:
        revision (str, optional): Target revision.
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
        sql (bool, optional): Return the SQL for a DBA to review and apply,
            without connecting to the database.

    Returns the applied revisions, or the SQL when ``sql`` is set.

    .. code-block:: bash

        salt-run sqlalchemy.upgrade
        salt-run sqlalchemy.upgrade sql=True
    """
    return salt.sqlalchemy.migrations.upgrade(
        revision, engine_name=target_engine, sql=sql
    )


def downgrade(revision, target_engine=None, sql=False):
    """
    Downgrade the schema to a revision. ``base`` removes every table.

    Args:
        revision (str): Target revision.
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
        sql (bool, optional): Return the SQL instead of running it.
    """
    return salt.sqlalchemy.migrations.downgrade(
        revision, engine_name=target_engine, sql=sql
    )


def current(target_engine=None):
    """
    Return the revisions applied to the database.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    return salt.sqlalchemy.migrations.current(engine_name=target_engine)


def history(target_engine=None):
    """
    Return the available revisions, newest first.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    return salt.sqlalchemy.migrations.history(engine_name=target_engine)


def stamp(revision, target_engine=None):
    """
    Record a revision as applied without running its migrations.

    Args:
        revision (str): Revision to record.
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    return salt.sqlalchemy.migrations.stamp(revision, engine_name=target_engine)


def rebuild_terms(full=False, batch=1000, target_engine=None):
    """
    Recompute the PostgreSQL targeting terms of cached grains and pillar.

    Run this after changing ``sqlalchemy.term_paths`` or
    ``sqlalchemy.term_exclude``, or after an offline (``sql=True``) upgrade.
    Targeting stays correct meanwhile, but rows whose terms do not match the
    configuration are rechecked on every lookup. Rows commit in batches, so
    the cache stays writable.

    Args:
        full (bool, optional): Rebuild every row, not only rows whose terms
            were built for another configuration.
        batch (int, optional): Rows per committed batch.
        target_engine (str, optional): Name of the engine to use. If None, default target is used.

    Returns the number of rows processed per bank. Rows a master stores
    during the rebuild keep the terms it wrote.

    .. code-block:: bash

        salt-run sqlalchemy.rebuild_terms
    """
    registry = salt.sqlalchemy.ENGINE_REGISTRY[
        salt.sqlalchemy._engine_name(target_engine)
    ]
    if registry["engine"].dialect.name != "postgresql":
        return {}
    config = registry["config"]
    with (
        registry["engine"].connect().execution_options(isolation_level="AUTOCOMMIT")
    ) as connection:
        return terms.rebuild(
            connection,
            config.get("schema") or None,
            terms.paths(config),
            stale_only=not full,
            batch=batch,
        )


def drop_all(target_engine=None):
    """
    Drop all tables in the configured SQLAlchemy database.

    Equivalent to ``sqlalchemy.downgrade base``.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    salt.sqlalchemy.migrations.downgrade("base", engine_name=target_engine)
    return True


def create_all(target_engine=None):
    """
    Create all tables in the configured SQLAlchemy database.

    Equivalent to ``sqlalchemy.upgrade``.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    salt.sqlalchemy.migrations.upgrade("head", engine_name=target_engine)
    return True
