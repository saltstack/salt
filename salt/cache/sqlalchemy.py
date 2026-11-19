"""
Cache plugin for SQLAlchemy
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import salt.sqlalchemy
from salt.exceptions import SaltCacheError
from salt.sqlalchemy import model_for

try:
    import sqlalchemy.exc
    from sqlalchemy import delete, func, insert, or_, select, tuple_, update
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.sql.functions import count

    from salt.sqlalchemy.models import utcnow
except ImportError:
    pass


if TYPE_CHECKING:
    __opts__ = {}
    __salt__: dict[str, Callable]


log = logging.getLogger(__name__)

__virtualname__ = "sqlalchemy"


def __virtual__():
    """
    Confirm that SQLAlchemy is setup
    """
    if not salt.sqlalchemy.orm_configured():
        salt.sqlalchemy.configure_orm(__opts__)
    return __virtualname__


def init_kwargs(kwargs):
    """
    init kwargs
    """
    cluster_id = kwargs.get("cluster_id", __opts__.get("cluster_id"))

    # we use cluster_id as a pk, None/null wont work
    if not cluster_id:
        cluster_id = salt.sqlalchemy.STANDALONE_CLUSTER

    return {
        "cluster_id": cluster_id,
        "engine_name": kwargs.get("engine_name"),
    }


def fetch(bank, key, cluster_id=None, expires=None, engine_name=None):
    """
    Fetch a key value.
    """
    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.read_session(bank, engine_name) as session:
        stmt = select(Cache).where(
            Cache.key == key,
            Cache.bank == bank,
            Cache.cluster == cluster_id,
            or_(
                Cache.expires_at.is_(None),
                Cache.expires_at > utcnow(),
            ),
        )

        result = session.execute(stmt).scalars().first()

        data = {}

        if result:
            data = result.data

        session.commit()

        return data


def store(bank, key, data, expires=None, cluster_id=None, engine_name=None):
    """
    Store a key value.
    """
    expires_at = None
    if expires:
        expires_at = datetime.datetime.now().astimezone() + datetime.timedelta(
            seconds=expires
        )
    elif isinstance(data, dict) and isinstance(data.get("expire"), (int, float)):
        # only convert if unix timestamp
        expires_at = datetime.datetime.fromtimestamp(
            data["expire"], tz=datetime.timezone.utc
        )

    log.trace(
        "storing %s:%s:%s:%s:%s",
        bank,
        key,
        data,
        expires_at,
        cluster_id,
    )

    Cache = model_for("Cache", engine_name=engine_name)
    values = {
        "key": key,
        "bank": bank,
        "cluster": cluster_id,
        "data": data,
        "expires_at": expires_at,
    }
    with salt.sqlalchemy.Session(engine_name) as session:
        stmt = _upsert_statement(Cache, session.bind.dialect.name, values)
        if stmt is None:
            _store_fallback(session, Cache, values)
        else:
            session.execute(stmt)
        session.commit()


def _upsert_statement(Cache, dialect, values):
    """Build one atomic cache upsert for each supported database."""
    make_insert = {
        "postgresql": pg_insert,
        "sqlite": sqlite_insert,
        "mysql": mysql_insert,
        "mariadb": mysql_insert,
    }.get(dialect)
    if make_insert is None:
        return None

    stmt = make_insert(Cache).values(**values)
    mysql = dialect in {"mysql", "mariadb"}
    incoming = stmt.inserted if mysql else stmt.excluded
    changes = {
        "data": incoming.data,
        "expires_at": incoming.expires_at,
        "created_at": utcnow(),
    }
    if mysql:
        return stmt.on_duplicate_key_update(**changes)
    return stmt.on_conflict_do_update(
        index_elements=Cache.__table__.primary_key.columns, set_=changes
    )


def _store_fallback(session, Cache, values):
    """Check affected rows and retry concurrent creation on other dialects."""
    identity = tuple(
        column == values[column.key] for column in Cache.__table__.primary_key
    )
    overwrite = (
        update(Cache)
        .where(*identity)
        .values(
            data=values["data"],
            expires_at=values["expires_at"],
            created_at=utcnow(),
        )
        .execution_options(synchronize_session=False)
    )
    for attempt in range(3):
        affected = session.execute(overwrite).rowcount
        if affected == 1:
            return
        if affected != 0:
            raise SaltCacheError("Cannot verify SQLAlchemy cache update row count")
        try:
            session.execute(insert(Cache).values(**values))
            return
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            # Only retry when a competing writer created this exact key.
            # Otherwise preserve the original constraint failure.
            if (
                attempt == 2
                or session.scalar(select(Cache.key).where(*identity)) is None
            ):
                raise


def _bank_startswith(column, prefix, dialect):
    # SQLite LIKE ignores ASCII case even with a binary column collation.
    if dialect.name == "sqlite":
        return func.substr(column, 1, len(prefix)) == prefix
    return column.startswith(prefix, autoescape=True)


def flush(bank, key=None, cluster_id=None, engine_name=None, **_):
    """
    Remove a key, or the bank and all its sub-banks when key is None.
    """
    log.trace("flushing %s:%s", bank, key)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.Session(engine_name) as session:
        bank = bank.rstrip("/")
        stmt = delete(Cache).where(Cache.cluster == cluster_id)
        if key is not None:
            stmt = stmt.where(Cache.bank == bank, Cache.key == key)
        elif bank:
            stmt = stmt.where(
                or_(
                    Cache.bank == bank,
                    _bank_startswith(Cache.bank, bank + "/", session.bind.dialect),
                )
            )

        session.execute(stmt)
        session.commit()


def list(bank, cluster_id=None, engine_name=None, **_):
    """
    Return the keys and immediate sub-bank names in the specified bank.
    """
    log.trace("listing %s, cluster: %s", bank, cluster_id)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.read_session(bank, engine_name) as session:
        bank = bank.rstrip("/")
        prefix = bank + "/" if bank else ""
        conditions = (
            Cache.cluster == cluster_id,
            or_(Cache.expires_at.is_(None), Cache.expires_at > utcnow()),
        )
        keys = set(
            session.execute(
                select(Cache.key).where(*conditions, Cache.bank == bank)
            ).scalars()
        )
        banks = session.execute(
            select(Cache.bank)
            .where(
                *conditions,
                Cache.bank != bank,
                _bank_startswith(Cache.bank, prefix, session.bind.dialect),
            )
            .distinct()
        ).scalars()
        keys.update(child[len(prefix) :].split("/", 1)[0] for child in banks)
        session.commit()
        return sorted(keys)


def list_all(bank, include_data=False, cluster_id=None, engine_name=None, **_):
    """Return live entries in this exact bank, including their decoded data."""
    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.read_session(bank, engine_name) as session:
        stmt = select(Cache.key, Cache.data).where(
            Cache.bank == bank,
            Cache.cluster == cluster_id,
            or_(Cache.expires_at.is_(None), Cache.expires_at > utcnow()),
        )
        entries = dict(session.execute(stmt).all())
        session.commit()
        return entries


def contains(bank, key, cluster_id=None, engine_name=None, **_):
    """
    Checks if the specified bank contains the specified key.
    """
    log.trace("check if %s in %s, cluster: %s", key, bank, cluster_id)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.read_session(bank, engine_name) as session:
        if key is None:
            bank = bank.rstrip("/")
            stmt = select(count()).where(
                Cache.cluster == cluster_id,
                or_(
                    Cache.expires_at.is_(None),
                    Cache.expires_at > utcnow(),
                ),
            )
            if bank:
                stmt = stmt.where(
                    or_(
                        Cache.bank == bank,
                        _bank_startswith(Cache.bank, bank + "/", session.bind.dialect),
                    )
                )
            key = session.execute(stmt).scalars().first()
            session.commit()
            return key > 0
        else:
            stmt = select(Cache.key).where(
                Cache.cluster == cluster_id,
                Cache.bank == bank,
                Cache.key == key,
                or_(
                    Cache.expires_at.is_(None),
                    Cache.expires_at > utcnow(),
                ),
            )
            key = session.execute(stmt).scalars().first()
            session.commit()
            return key is not None


def updated(bank, key, cluster_id=None, engine_name=None, **_):
    """
    Given a bank and key, return the epoch of the created_at.
    """
    log.trace("returning epoch key %s at %s, cluster: %s", key, bank, cluster_id)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.read_session(bank, engine_name) as session:
        stmt = select(Cache.created_at).where(
            Cache.cluster == cluster_id,
            Cache.bank == bank,
            Cache.key == key,
        )
        created_at = session.execute(stmt).scalars().first()
        session.commit()

        if created_at:
            return created_at.timestamp()


def clean_expired(bank, cluster_id=None, limit=None, engine_name=None, **_):
    """
    Delete keys from a bank that has expired keys if the
    'expires_at' column is not null.
    """
    log.trace(
        "sqlalchemy.clean_expired: removing expired keys at bank %s, cluster: %s",
        bank,
        cluster_id,
    )

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.Session(engine_name) as session:
        conditions = (
            Cache.cluster == cluster_id,
            Cache.bank == bank,
            (Cache.expires_at.isnot(None)) & (Cache.expires_at <= utcnow()),
        )
        stmt = delete(Cache).where(*conditions)

        if limit:
            dialect = session.bind.dialect.name
            if dialect in {"mysql", "mariadb"}:
                stmt = stmt.with_dialect_options(**{f"{dialect}_limit": limit})
            else:
                subq = (
                    select(Cache.bank, Cache.key, Cache.cluster)
                    .where(*conditions)
                    .limit(limit)
                )
                stmt = stmt.where(
                    tuple_(Cache.bank, Cache.key, Cache.cluster).in_(subq)
                )

        session.execute(stmt.execution_options(synchronize_session=False))
        session.commit()
