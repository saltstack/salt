"""
Salt runner for managing SQLAlchemy database schema.

Provides runners to create or drop all tables using the current SQLAlchemy configuration.
"""

import logging

import salt.sqlalchemy

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


def drop_all(target_engine=None):
    """
    Drop all tables in the configured SQLAlchemy database.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    with salt.sqlalchemy.Session(target_engine) as session:
        salt.sqlalchemy.drop_all()
        session.commit()

    return True


def create_all(target_engine=None):
    """
    Create all tables in the configured SQLAlchemy database.

    Args:
        target_engine (str, optional): Name of the engine to use. If None, default target is used.
    """
    with salt.sqlalchemy.Session(target_engine) as session:
        salt.sqlalchemy.create_all()
        session.commit()

    return True
