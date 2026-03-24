"""
Cache plugin for SQLAlchemy
"""

import datetime
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import salt.exceptions
import salt.sqlalchemy
from salt.sqlalchemy import model_for

try:
    import sqlalchemy.exc
    from sqlalchemy import delete, insert, or_, select, tuple_, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.sql.functions import count, now
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
    try:
        if not salt.sqlalchemy.orm_configured():
            salt.sqlalchemy.configure_orm(__opts__)
    except salt.exceptions.SaltException as exc:
        log.error("Failed to configure_orm: %s", str(exc))
        return False

    return __virtualname__


def init_kwargs(kwargs):
    """
    init kwargs
    """
    cluster_id = kwargs.get("cluster_id", __opts__["cluster_id"])

    # we use cluster_id as a pk, None/null wont work
    if not cluster_id:
        cluster_id = "null"

    return {
        "cluster_id": cluster_id,
        "expires": kwargs.get("expires"),
        "engine_name": kwargs.get("engine_name"),
    }


def fetch(bank, key, cluster_id=None, expires=None, engine_name=None):
    """
    Fetch a key value.
    """
    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.ROSession(engine_name) as session:
        stmt = select(Cache).where(
            Cache.key == key,
            Cache.bank == bank,
            Cache.cluster == cluster_id,
            or_(
                Cache.expires_at.is_(None),
                Cache.expires_at >= now(),
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
    if expires:
        expires_at = datetime.datetime.now().astimezone() + datetime.timedelta(
            seconds=expires
        )
    elif isinstance(data, dict) and "expire" in data:
        if isinstance(data["expire"], float):
            # only convert if unix timestamp
            expires_at = datetime.datetime.fromtimestamp(data["expire"]).isoformat()
    else:
        expires_at = None

    log.trace(
        "storing %s:%s:%s:%s:%s",
        bank,
        key,
        data,
        expires_at,
        cluster_id,
    )

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.Session(engine_name) as session:
        if session.bind.dialect.name == "postgresql":
            stmt = pg_insert(Cache).values(
                key=key,
                bank=bank,
                data=data,
                expires_at=expires_at,
                cluster=cluster_id,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Cache.cluster, Cache.bank, Cache.key],
                set_=dict(
                    data=stmt.excluded.data,
                    expires_at=stmt.excluded.expires_at,
                    created_at=now(),
                ),
            )

            session.execute(stmt)
            session.commit()
        else:
            # the default path is racy, so any implementation specific upsert is preferred
            try:
                stmt = insert(Cache).values(
                    key=key, bank=bank, cluster=cluster_id, data=data
                )
                session.execute(stmt)
                session.commit()
            except sqlalchemy.exc.IntegrityError:
                session.rollback()

                stmt = (
                    update(Cache)
                    .where(
                        Cache.key == key,
                        Cache.bank == bank,
                        Cache.cluster == cluster_id,
                    )
                    .values(data=data)
                )
                session.execute(stmt)
                session.commit()


def flush(bank, key=None, cluster_id=None, engine_name=None, **_):
    """
    Remove the key from the cache bank with all the key content.
    """
    log.trace("flushing %s:%s", bank, key)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.Session(engine_name) as session:
        stmt = delete(Cache).where(Cache.cluster == cluster_id, Cache.bank == bank)

        if key:
            stmt = stmt.where(Cache.key == key)

        session.execute(stmt)
        session.commit()


def list(bank, cluster_id=None, engine_name=None, **_):
    """
    Return an iterable object containing all entries stored in the specified
    bank.
    """
    log.trace("listing %s, cluster: %s", bank, cluster_id)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.ROSession(engine_name) as session:
        stmt = (
            select(Cache.key)
            .where(
                Cache.cluster == cluster_id,
                Cache.bank == bank,
                or_(
                    Cache.expires_at.is_(None),
                    Cache.expires_at >= now(),
                ),
            )
            .order_by(Cache.key)
        )
        keys = session.execute(stmt).scalars().all()
        session.commit()
        return keys


def contains(bank, key, cluster_id=None, engine_name=None, **_):
    """
    Checks if the specified bank contains the specified key.
    """
    log.trace("check if %s in %s, cluster: %s", key, bank, cluster_id)

    Cache = model_for("Cache", engine_name=engine_name)
    with salt.sqlalchemy.ROSession(engine_name) as session:
        if key is None:
            stmt = select(count()).where(
                Cache.cluster == cluster_id,
                Cache.bank == bank,
                or_(
                    Cache.expires_at.is_(None),
                    Cache.expires_at >= now(),
                ),
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
                    Cache.expires_at >= now(),
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
    with salt.sqlalchemy.ROSession(engine_name) as session:
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
        subq = select(Cache.bank, Cache.key, Cache.cluster).where(
            Cache.cluster == cluster_id,
            Cache.bank == bank,
            (Cache.expires_at.isnot(None)) & (Cache.expires_at <= now()),
        )

        if limit:
            subq = subq.limit(limit)

        stmt = (
            delete(Cache)
            .where(tuple_(Cache.bank, Cache.key, Cache.cluster).in_(subq))
            .returning(Cache.key)
        )

        result = session.execute(stmt)
        expired = result.scalars().all()
        session.commit()
        return expired
