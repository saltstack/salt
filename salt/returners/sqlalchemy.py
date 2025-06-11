"""
Returner plugin for SQLAlchemy.
"""

import functools
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import salt.exceptions
import salt.sqlalchemy
import salt.utils.jid
import salt.utils.job
from salt.sqlalchemy import model_for

try:
    import sqlalchemy.exc
    from sqlalchemy import BigInteger, cast, delete, func, insert, literal, select
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
except ImportError:
    pass

if TYPE_CHECKING:
    __opts__ = {}
    __context__ = {}
    __salt__: dict[str, Callable]


log = logging.getLogger(__name__)

__virtualname__ = "sqlalchemy"


def __virtual__():
    """
    Ensure that SQLAlchemy ORM is configured and ready.
    """
    if not salt.sqlalchemy.orm_configured():
        salt.sqlalchemy.configure_orm(__opts__)
    return __virtualname__


def retry_on_failure(f):
    """
    Simple decorator to retry on OperationalError/InterfaceError
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        """
        Wrapper function that implements retry logic for database operations.
        """
        tries = __opts__.get("returner.sqlalchemy.max_retries")
        tries = 15 if tries is None else tries
        delay = __opts__.get("returner.sqlalchemy.retry_delay")
        delay = 5 if delay is None else delay
        if tries < 1:
            raise salt.exceptions.SaltConfigurationError(
                "returner.sqlalchemy.max_retries must be positive"
            )
        for attempt in range(tries):
            try:
                return f(*args, **kwargs)
            except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InterfaceError):
                if attempt + 1 == tries:
                    log.exception(
                        "SQLAlchemy %s failed after %s attempts", f.__name__, tries
                    )
                    raise
                time.sleep(delay)

    return wrapper


def _cluster_id():
    return __opts__.get("cluster_id") or salt.sqlalchemy.STANDALONE_CLUSTER


def _jid_created_at(jid):
    if not salt.utils.jid.is_jid(str(jid)):
        raise salt.exceptions.SaltInvocationError(f"Invalid JID: {jid}")
    try:
        return datetime.strptime(str(jid)[:20], "%Y%m%d%H%M%S%f").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise salt.exceptions.SaltInvocationError(f"Invalid JID: {jid}") from exc


def _jid_expired(created_at):
    retention = int(salt.utils.job.get_keep_jobs_seconds(__opts__))
    return retention > 0 and created_at < datetime.now(timezone.utc) - timedelta(
        seconds=retention
    )


def _insert_missing(model, dialect):
    """Ignore duplicate identities without suppressing other write errors."""
    if dialect in {"postgresql", "sqlite"}:
        make_insert = pg_insert if dialect == "postgresql" else sqlite_insert
        return make_insert(model).on_conflict_do_nothing(
            index_elements=model.__table__.primary_key.columns
        )
    if dialect in {"mysql", "mariadb"}:
        stmt = mysql_insert(model)
        return stmt.on_duplicate_key_update(jid=stmt.inserted.jid)
    raise salt.exceptions.SaltInvocationError(
        f"Unsupported SQLAlchemy dialect: {dialect}"
    )


@retry_on_failure
def returner(ret):
    """
    Return data to returns in database
    """
    Returns = model_for("Returns", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        fun = ret["fun"]
        success = ret.get("success", False)
        if isinstance(fun, (list, tuple)):
            fun = ",".join(fun)
        if isinstance(success, dict):
            success = all(success.values())
        elif isinstance(success, (list, tuple)):
            success = all(success)
        record = {
            "cluster": _cluster_id(),
            "fun": fun,
            "jid": ret["jid"],
            "id": ret["id"],
            "success": bool(success),
            "ret": ret,
        }

        session.execute(insert(Returns), [record])
        session.commit()


@retry_on_failure
def event_return(evts, tries=None):
    """
    Return event to database server

    Requires that configuration be enabled via 'event_return'
    option in master config.
    """
    Events = model_for("Events", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        records = []
        for evt in evts:
            record = {
                "tag": evt.get("tag", ""),
                "data": evt.get("data", ""),
                "cluster": _cluster_id(),
                "master_id": __opts__["id"],
            }

            try:
                record["created_at"] = evt["data"]["_stamp"]
            except (KeyError, TypeError):
                pass

            records.append(record)

        session.execute(insert(Events), records)
        session.commit()


@retry_on_failure
def save_load(jid, load, minions=None):
    """
    Save the load to the specified jid id
    """
    created_at = _jid_created_at(jid)
    if _jid_expired(created_at):
        return

    Jids = model_for("Jids", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        record = {
            "jid": str(jid),
            "load": load,
            "minions": minions or [],
            "cluster": _cluster_id(),
            "created_at": created_at,
        }

        session.execute(_insert_missing(Jids, session.bind.dialect.name), [record])
        session.commit()


@retry_on_failure
def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """Merge discovered minions without rewriting the original publish load."""
    created_at = _jid_created_at(jid)
    if _jid_expired(created_at):
        return
    records = [
        {
            "jid": str(jid),
            "cluster": _cluster_id(),
            "created_at": created_at,
            "minion_id": minion,
        }
        for minion in dict.fromkeys(minions)
    ]
    if not records:
        return
    JidMinions = model_for("JidMinions", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        session.execute(_insert_missing(JidMinions, session.bind.dialect.name), records)
        session.commit()


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    Jids, JidMinions = model_for(
        "Jids", "JidMinions", engine_name=__context__.get("engine_name")
    )
    try:
        created_at = _jid_created_at(jid)
    except salt.exceptions.SaltInvocationError:
        return {}
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        stmt = select(Jids).where(
            Jids.jid == str(jid),
            Jids.cluster == _cluster_id(),
            Jids.created_at == created_at,
        )
        result = session.execute(stmt).first()
        load = {}
        if result:
            jid = result[0]
            load = dict(jid.load)
            minions = dict.fromkeys(jid.minions or [])
            discovered = session.scalars(
                select(JidMinions.minion_id)
                .where(
                    JidMinions.jid == jid.jid,
                    JidMinions.cluster == jid.cluster,
                    JidMinions.created_at == created_at,
                )
                .order_by(JidMinions.minion_id)
            )
            minions.update((minion, None) for minion in discovered)
            load["Minions"] = list(minions)
        session.commit()
        return load


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    Returns = model_for("Returns", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        stmt = (
            select(Returns.id, Returns.ret)
            .where(Returns.jid == str(jid), Returns.cluster == _cluster_id())
            .order_by(Returns.created_at)
        )
        results = session.execute(stmt).all()

        ret = {}
        for result in results:
            ret[result.id] = result.ret

        session.commit()

        return ret


def get_fun(fun):
    """
    Return a dict of the last function called for all minions
    """
    # this could be done with a separate table, but why?
    raise salt.exceptions.SaltException(
        "This is too costly to run via database at the moment, left unimplemented"
    )


def get_jids(last=None):
    """
    Return a list of all job ids
    """
    # this could be done, but why would you ever?
    raise salt.exceptions.SaltException("This is too costly to run, left unimplemented")


def get_minions():
    """
    Return a list of minions
    """
    raise salt.exceptions.SaltException("Use salt.util.minions._all_minions instead")


def prep_jid(
    nocache=False,
    passed_jid=None,
    retry_count=0,
):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    Use microsecond UTC database timestamps and advisory locks to reduce
    concurrent collisions. Locks do not reserve JIDs after release.
    """
    # this will return false for "req" salt-call jid
    if salt.utils.jid.is_jid(passed_jid):
        return passed_jid
    if __opts__.get("unique_jid", False):
        return salt.utils.jid.gen_jid(__opts__)

    # generate a candidate JID
    jid = salt.utils.jid.gen_jid(__opts__)

    try:
        with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
            if session.bind.dialect.name == "postgresql":
                candidate = select(
                    func.to_char(
                        func.timezone("UTC", func.clock_timestamp()),
                        "YYYYMMDDHH24MISSUS",
                    ).label("jid")
                ).cte("jid_candidate")
                jid_expr = candidate.c.jid

                lock_expr = func.pg_try_advisory_xact_lock(
                    cast(func.hashtext(jid_expr), BigInteger)
                )
            elif session.bind.dialect.name in {"mysql", "mariadb"}:
                jid_expr = func.DATE_FORMAT(
                    func.UTC_TIMESTAMP(6), literal("%Y%m%d%H%i%s%f")
                )

                # Apply GET_LOCK(jid_expr, 0) for non-blocking lock attempt
                lock_expr = func.GET_LOCK(jid_expr, literal(0))
            elif session.bind.dialect.name == "sqlite":
                # sqlite doesn't require locking
                return jid

            else:
                raise salt.exceptions.SaltException("Unrecognized dialect")

            stmt = select(lock_expr.label("locked"), jid_expr.label("jid"))

            result = session.execute(stmt).one()
            locked, jid = result.locked, result.jid

            if locked:
                # lock acquired, return the generated jid
                if session.bind.dialect.name in {"mysql", "mariadb"}:
                    # mysql needs a manual lock release
                    stmt = select(func.RELEASE_LOCK(literal(jid)).label("released"))
                    session.execute(stmt).one()

                session.commit()
                return jid
            else:
                # lock contention, retry with a new jid
                if retry_count < 5:
                    return prep_jid(
                        nocache=nocache, passed_jid=None, retry_count=retry_count + 1
                    )
                else:
                    log.warning(
                        "Maximum retry attempts reached for prep_jid lock acquisition"
                    )
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "Something went wrong trying to prep jid (unable to acquire lock?), falling back to salt.utils.jid.gen_jid()"
        )

    # we failed to get a unique jid, just return one
    # without asserting global uniqueness
    return salt.utils.jid.gen_jid(__opts__)


def clean_old_jobs():
    """
    Called in the master's event loop every loop_interval. Removes data older
    than the configured keep_jobs_seconds setting from the database tables.
    When configured, uses partitioning for efficient data lifecycle management.

    Returns:
        bool: True if cleaning was performed, None if no action was taken
    """
    keep_jobs_seconds = int(salt.utils.job.get_keep_jobs_seconds(__opts__))
    if keep_jobs_seconds > 0:
        if __opts__.get("archive_jobs", False):
            raise salt.exceptions.SaltException(
                "This is unimplemented. Use pg_partman or other native partition handling"
            )
        else:
            models = model_for(
                "Jids",
                "JidMinions",
                "Returns",
                "Events",
                engine_name=__context__.get("engine_name"),
            )
            ttl = datetime.now(timezone.utc) - timedelta(seconds=keep_jobs_seconds)

            with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
                for model in models:
                    session.execute(
                        delete(model).where(
                            model.created_at < ttl, model.cluster == _cluster_id()
                        )
                    )
                session.commit()

            return True
