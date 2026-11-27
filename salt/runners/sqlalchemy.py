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
