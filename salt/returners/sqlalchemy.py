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
    try:
        if not salt.sqlalchemy.orm_configured():
            salt.sqlalchemy.configure_orm(__opts__)
    except salt.exceptions.SaltException as exc:
        log.error("Failed to configure_orm: %s", str(exc))
        return False

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
        tries = __opts__["returner.sqlalchemy.max_retries"]
        for _ in range(0, tries):
            try:
                return f(*args, **kwargs)
            except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InterfaceError):
                time.sleep(__opts__["returner.sqlalchemy.retry_delay"])

    return wrapper


@retry_on_failure
def returner(ret):
    """
    Return data to returns in database
    """
    Returns = model_for("Returns", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        record = {
            "cluster": __opts__["cluster_id"],
            "fun": ret["fun"],
            "jid": ret["jid"],
            "id": ret["id"],
            "success": ret.get("success", False),
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
                "cluster": __opts__["cluster_id"],
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
    if not minions:
        minions = []

    Jids = model_for("Jids", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
        record = {
            "jid": jid,
            "load": load,
            "minions": minions,
            "cluster": __opts__["cluster_id"],
        }

        session.execute(insert(Jids), [record])
        session.commit()


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """
    Included for API consistency
    """


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    Jids = model_for("Jids", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.ROSession(__context__.get("engine_name")) as session:
        # Use to_jsonb for jsonb conversion in Postgres
        stmt = select(Jids).where(Jids.jid == str(jid))
        result = session.execute(stmt).first()
        load = {}
        if result:
            jid = result[0]
            load = jid.load
            load["Minions"] = jid.minions or []
        session.commit()
        return load


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    Returns = model_for("Returns", engine_name=__context__.get("engine_name"))
    with salt.sqlalchemy.ROSession(__context__.get("engine_name")) as session:
        stmt = select(Returns.id, Returns.ret).where(Returns.jid == str(jid))
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
    nocache=False, passed_jid=None, retry_count=0
):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    Using a recursive retry approach with advisory locks to avoid table contention
    Locking guaruntees a global unique jid on postgresql and mysql.
    """
    # this will return false for "req" salt-call jid
    if salt.utils.jid.is_jid(passed_jid):
        return passed_jid

    # generate a candidate JID
    jid = salt.utils.jid.gen_jid(__opts__)

    try:
        with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
            if session.bind.dialect.name == "postgresql":
                jid_expr = func.to_char(func.clock_timestamp(), "YYYYMMDDHH24MISSUS")

                lock_expr = func.pg_try_advisory_xact_lock(
                    cast(func.abs(func.hashtext(jid_expr)), BigInteger)
                )
            elif session.bind.dialect.name == "mysql":
                # Build the DATE_FORMAT(NOW(3), '%Y%m%d%H%i%s%f') expression
                jid_expr = func.DATE_FORMAT(func.NOW(3), literal("%Y%m%d%H%i%s%f"))

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
                if session.bind.dialect.name == "mysql":
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
            Jids, Returns, Events = model_for(
                "Jids", "Returns", "Events", engine_name=__context__.get("engine_name")
            )
            ttl = datetime.now(timezone.utc) - timedelta(seconds=keep_jobs_seconds)

            with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
                stmt = delete(Jids).where(
                    Jids.created_at < ttl, Jids.cluster == __opts__["cluster_id"]
                )
                session.execute(stmt)
                session.commit()

            with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
                stmt = delete(Returns).where(
                    Returns.created_at < ttl, Returns.cluster == __opts__["cluster_id"]
                )
                session.execute(stmt)
                session.commit()

            with salt.sqlalchemy.Session(__context__.get("engine_name")) as session:
                stmt = delete(Events).where(
                    Events.created_at < ttl, Events.cluster == __opts__["cluster_id"]
                )
                session.execute(stmt)
                session.commit()

            return True
