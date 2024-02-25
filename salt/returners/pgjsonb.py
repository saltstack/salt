"""
Return data to a PostgreSQL server with json data stored in Pg's jsonb data type

:maintainer:    Dave Boucha <dave@saltstack.com>, Seth House <shouse@saltstack.com>, C. R. Oldham <cr@saltstack.com>
:maturity:      Stable
:depends:       python-psycopg2
:platform:      all

.. note::
    There are three PostgreSQL returners.  Any can function as an external
    :ref:`master job cache <external-job-cache>`. but each has different
    features.  SaltStack recommends
    :mod:`returners.pgjsonb <salt.returners.pgjsonb>` if you are working with
    a version of PostgreSQL that has the appropriate native binary JSON types.
    Otherwise, review
    :mod:`returners.postgres <salt.returners.postgres>` and
    :mod:`returners.postgres_local_cache <salt.returners.postgres_local_cache>`
    to see which module best suits your particular needs.

To enable this returner, the minion will need the python client for PostgreSQL
installed and the following values configured in the minion or master
config. These are the defaults:

.. code-block:: yaml

    returner.pgjsonb.host: 'salt'
    returner.pgjsonb.user: 'salt'
    returner.pgjsonb.pass: 'salt'
    returner.pgjsonb.db: 'salt'
    returner.pgjsonb.port: 5432

SSL is optional. The defaults are set to None. If you do not want to use SSL,
either exclude these options or set them to None.

.. code-block:: yaml

    returner.pgjsonb.sslmode: None
    returner.pgjsonb.sslcert: None
    returner.pgjsonb.sslkey: None
    returner.pgjsonb.sslrootcert: None
    returner.pgjsonb.sslcrl: None

.. versionadded:: 2017.5.0

Alternative configuration values can be used by prefacing the configuration
with `alternative.`. Any values not found in the alternative configuration will
be pulled from the default location. As stated above, SSL configuration is
optional. The following ssl options are simply for illustration purposes:

.. code-block:: yaml

    alternative.pgjsonb.host: 'salt'
    alternative.pgjsonb.user: 'salt'
    alternative.pgjsonb.pass: 'salt'
    alternative.pgjsonb.db: 'salt'
    alternative.pgjsonb.port: 5432
    alternative.pgjsonb.ssl_ca: '/etc/pki/mysql/certs/localhost.pem'
    alternative.pgjsonb.ssl_cert: '/etc/pki/mysql/certs/localhost.crt'
    alternative.pgjsonb.ssl_key: '/etc/pki/mysql/certs/localhost.key'

Should you wish the returner data to be cleaned out every so often, set
``keep_jobs_seconds`` to the number of seconds for the jobs to live in the tables.
Setting it to ``0`` or leaving it unset will cause the data to stay in the tables.

Should you wish to archive jobs in a different table for later processing,
set ``archive_jobs`` to True.  Salt will create 3 archive tables;

- ``jids_archive``
- ``salt_returns_archive``
- ``salt_events_archive``

and move the contents of ``jids``, ``salt_returns``, and ``salt_events`` that are
more than ``keep_jobs_seconds`` seconds old to these tables.

.. versionadded:: 2019.2.0

Use the following Pg database schema:

.. code-block:: sql

    CREATE DATABASE  salt
      WITH ENCODING 'utf-8';

    --
    -- Table structure for table `jids`
    --
    DROP TABLE IF EXISTS jids;
    CREATE TABLE jids (
       jid varchar(255) NOT NULL primary key,
       load jsonb NOT NULL
    );
    CREATE INDEX idx_jids_jsonb on jids
           USING gin (load)
           WITH (fastupdate=on);

    --
    -- Table structure for table `salt_returns`
    --

    DROP TABLE IF EXISTS salt_returns;
    CREATE TABLE salt_returns (
      fun varchar(50) NOT NULL,
      jid varchar(255) NOT NULL,
      return jsonb NOT NULL,
      id varchar(255) NOT NULL,
      success varchar(10) NOT NULL,
      full_ret jsonb NOT NULL,
      alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW());

    CREATE INDEX idx_salt_returns_id ON salt_returns (id);
    CREATE INDEX idx_salt_returns_jid ON salt_returns (jid);
    CREATE INDEX idx_salt_returns_fun ON salt_returns (fun);
    CREATE INDEX idx_salt_returns_return ON salt_returns
        USING gin (return) with (fastupdate=on);
    CREATE INDEX idx_salt_returns_full_ret ON salt_returns
        USING gin (full_ret) with (fastupdate=on);

    --
    -- Table structure for table `salt_events`
    --

    DROP TABLE IF EXISTS salt_events;
    DROP SEQUENCE IF EXISTS seq_salt_events_id;
    CREATE SEQUENCE seq_salt_events_id;
    CREATE TABLE salt_events (
        id BIGINT NOT NULL UNIQUE DEFAULT nextval('seq_salt_events_id'),
        tag varchar(255) NOT NULL,
        data jsonb NOT NULL,
        alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        master_id varchar(255) NOT NULL);

    CREATE INDEX idx_salt_events_tag on
        salt_events (tag);
    CREATE INDEX idx_salt_events_data ON salt_events
        USING gin (data) with (fastupdate=on);

Required python modules: Psycopg2

To use this returner, append '--return pgjsonb' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return pgjsonb

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return pgjsonb --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return pgjsonb --return_kwargs '{"db": "another-salt"}'

"""

import logging
import sys
import time
from contextlib import contextmanager

import salt.exceptions
import salt.returners
import salt.utils.data
import salt.utils.job

try:
    import psycopg2
    import psycopg2.extras

    HAS_PG = True
except ImportError:
    HAS_PG = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pgjsonb"

PG_SAVE_LOAD_SQL = """INSERT INTO jids (jid, load) VALUES (%(jid)s, %(load)s)"""


def __virtual__():
    if not HAS_PG:
        return (
            False,
            "Could not import pgjsonb returner; python-psycopg2 is not installed.",
        )
    return True


def _get_options(ret=None):
    """
    Returns options used for the MySQL connection.
    """
    defaults = {
        "host": "localhost",
        "user": "salt",
        "pass": "salt",
        "db": "salt",
        "port": 5432,
    }

    attrs = {
        "host": "host",
        "user": "user",
        "pass": "pass",
        "db": "db",
        "port": "port",
        "sslmode": "sslmode",
        "sslcert": "sslcert",
        "sslkey": "sslkey",
        "sslrootcert": "sslrootcert",
        "sslcrl": "sslcrl",
    }

    _options = salt.returners.get_returner_options(
        f"returner.{__virtualname__}",
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults,
    )
    # Ensure port is an int
    if "port" in _options:
        _options["port"] = int(_options["port"])
    return _options


@contextmanager
def _get_serv(ret=None, commit=False):
    """
    Return a Pg cursor
    """
    _options = _get_options(ret)
    try:
        # An empty ssl_options dictionary passed to MySQLdb.connect will
        # effectively connect w/o SSL.
        ssl_options = {
            k: v
            for k, v in _options.items()
            if k in ["sslmode", "sslcert", "sslkey", "sslrootcert", "sslcrl"]
        }
        conn = psycopg2.connect(
            host=_options.get("host"),
            port=_options.get("port"),
            dbname=_options.get("db"),
            user=_options.get("user"),
            password=_options.get("pass"),
            **ssl_options,
        )
    except psycopg2.OperationalError as exc:
        raise salt.exceptions.SaltMasterError(
            f"pgjsonb returner could not connect to database: {exc}"
        )

    if conn.server_version is not None and conn.server_version >= 90500:
        global PG_SAVE_LOAD_SQL
        PG_SAVE_LOAD_SQL = """INSERT INTO jids
                              (jid, load)
                              VALUES (%(jid)s, %(load)s)
                              ON CONFLICT (jid) DO UPDATE
                              SET load=%(load)s"""

    cursor = conn.cursor()

    try:
        yield cursor
    except psycopg2.DatabaseError as err:
        error = err.args
        sys.stderr.write(str(error))
        cursor.execute("ROLLBACK")
        raise
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")
    finally:
        conn.close()


def returner(ret):
    """
    Return data to a Pg server
    """
    try:
        with _get_serv(ret, commit=True) as cur:
            sql = """INSERT INTO salt_returns
                    (fun, jid, return, id, success, full_ret, alter_time)
                    VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s))"""

            cleaned_return = salt.utils.data.decode(ret)
            cur.execute(
                sql,
                (
                    ret["fun"],
                    ret["jid"],
                    psycopg2.extras.Json(cleaned_return["return"]),
                    ret["id"],
                    ret.get("success", False),
                    psycopg2.extras.Json(cleaned_return),
                    time.time(),
                ),
            )
    except salt.exceptions.SaltMasterError:
        log.critical(
            "Could not store return with pgjsonb returner. PostgreSQL server"
            " unavailable."
        )


def event_return(events):
    """
    Return event to Pg server

    Requires that configuration be enabled via 'event_return'
    option in master config.
    """
    with _get_serv(events, commit=True) as cur:
        for event in events:
            tag = event.get("tag", "")
            data = event.get("data", "")
            sql = """INSERT INTO salt_events (tag, data, master_id, alter_time)
                     VALUES (%s, %s, %s, to_timestamp(%s))"""
            cur.execute(
                sql, (tag, psycopg2.extras.Json(data), __opts__["id"], time.time())
            )


def save_load(jid, load, minions=None):
    """
    Save the load to the specified jid id
    """
    with _get_serv(commit=True) as cur:
        load = salt.utils.data.decode(load)
        try:
            cur.execute(
                PG_SAVE_LOAD_SQL, {"jid": jid, "load": psycopg2.extras.Json(load)}
            )
        except psycopg2.IntegrityError:
            # https://github.com/saltstack/salt/issues/22171
            # Without this try/except we get tons of duplicate entry errors
            # which result in job returns not being stored properly
            pass


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """
    Included for API consistency
    """


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT load FROM jids WHERE jid = %s;"""
        cur.execute(sql, (jid,))
        data = cur.fetchone()
        if data:
            return data[0]
        return {}


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT id, full_ret FROM salt_returns
                WHERE jid = %s"""

        cur.execute(sql, (jid,))
        data = cur.fetchall()
        ret = {}
        if data:
            for minion, full_ret in data:
                ret[minion] = full_ret
        return ret


def get_fun(fun):
    """
    Return a dict of the last function called for all minions
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT s.id,s.jid, s.full_ret
                FROM salt_returns s
                JOIN ( SELECT MAX(`jid`) as jid
                    from salt_returns GROUP BY fun, id) max
                ON s.jid = max.jid
                WHERE s.fun = %s
                """

        cur.execute(sql, (fun,))
        data = cur.fetchall()

        ret = {}
        if data:
            for minion, _, full_ret in data:
                ret[minion] = full_ret
        return ret


def get_jids():
    """
    Return a list of all job ids
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT jid, load
                FROM jids"""

        cur.execute(sql)
        data = cur.fetchall()
        ret = {}
        for jid, load in data:
            ret[jid] = salt.utils.jid.format_jid_instance(jid, load)
        return ret


def get_minions():
    """
    Return a list of minions
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT DISTINCT id
                FROM salt_returns"""

        cur.execute(sql)
        data = cur.fetchall()
        ret = []
        for minion in data:
            ret.append(minion[0])
        return ret


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    """
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)


def _purge_jobs(timestamp):
    """
    Purge records from the returner tables.
    :param job_age_in_seconds:  Purge jobs older than this
    :return:
    """
    with _get_serv() as cursor:
        try:
            sql = (
                "delete from jids where jid in (select distinct jid from salt_returns"
                " where alter_time < %s)"
            )
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err

        try:
            sql = "delete from salt_returns where alter_time < %s"
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err

        try:
            sql = "delete from salt_events where alter_time < %s"
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err

    return True


def _archive_jobs(timestamp):
    """
    Copy rows to a set of backup tables, then purge rows.
    :param timestamp: Archive rows older than this timestamp
    :return:
    """
    source_tables = ["jids", "salt_returns", "salt_events"]

    with _get_serv() as cursor:
        target_tables = {}
        for table_name in source_tables:
            try:
                tmp_table_name = table_name + "_archive"
                sql = "create table IF NOT exists {} (LIKE {})".format(
                    tmp_table_name, table_name
                )
                cursor.execute(sql)
                cursor.execute("COMMIT")
                target_tables[table_name] = tmp_table_name
            except psycopg2.DatabaseError as err:
                error = err.args
                sys.stderr.write(str(error))
                cursor.execute("ROLLBACK")
                raise err

        try:
            sql = (
                "insert into {} select * from {} where jid in (select distinct jid from"
                " salt_returns where alter_time < %s)".format(
                    target_tables["jids"], "jids"
                )
            )
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err
        except Exception as e:  # pylint: disable=broad-except
            log.error(e)
            raise

        try:
            sql = "insert into {} select * from {} where alter_time < %s".format(
                target_tables["salt_returns"], "salt_returns"
            )
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err

        try:
            sql = "insert into {} select * from {} where alter_time < %s".format(
                target_tables["salt_events"], "salt_events"
            )
            cursor.execute(sql, (timestamp,))
            cursor.execute("COMMIT")
        except psycopg2.DatabaseError as err:
            error = err.args
            sys.stderr.write(str(error))
            cursor.execute("ROLLBACK")
            raise err

    return _purge_jobs(timestamp)


def clean_old_jobs():
    """
    Called in the master's event loop every loop_interval.  Archives and/or
    deletes the events and job details from the database.
    :return:
    """
    keep_jobs_seconds = int(salt.utils.job.get_keep_jobs_seconds(__opts__))
    if keep_jobs_seconds > 0:
        try:
            with _get_serv() as cur:
                sql = "select (NOW() -  interval '{}' second) as stamp;".format(
                    keep_jobs_seconds
                )
                cur.execute(sql)
                rows = cur.fetchall()
                stamp = rows[0][0]

            if __opts__.get("archive_jobs", False):
                _archive_jobs(stamp)
            else:
                _purge_jobs(stamp)
        except Exception as e:  # pylint: disable=broad-except
            log.error(e)
