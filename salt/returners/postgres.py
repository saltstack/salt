"""
Return data to a postgresql server

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

:maintainer:    None
:maturity:      New
:depends:       psycopg2
:platform:      all

To enable this returner the minion will need the psycopg2 installed and
the following values configured in the minion or master config:

.. code-block:: yaml

    returner.postgres.host: 'salt'
    returner.postgres.user: 'salt'
    returner.postgres.passwd: 'salt'
    returner.postgres.db: 'salt'
    returner.postgres.port: 5432

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    alternative.returner.postgres.host: 'salt'
    alternative.returner.postgres.user: 'salt'
    alternative.returner.postgres.passwd: 'salt'
    alternative.returner.postgres.db: 'salt'
    alternative.returner.postgres.port: 5432

Running the following commands as the postgres user should create the database
correctly:

.. code-block:: sql

    psql << EOF
    CREATE ROLE salt WITH PASSWORD 'salt';
    CREATE DATABASE salt WITH OWNER salt;
    EOF

    psql -h localhost -U salt << EOF
    --
    -- Table structure for table 'jids'
    --

    DROP TABLE IF EXISTS jids;
    CREATE TABLE jids (
      jid   varchar(20) PRIMARY KEY,
      load  text NOT NULL
    );

    --
    -- Table structure for table 'salt_returns'
    --

    DROP TABLE IF EXISTS salt_returns;
    CREATE TABLE salt_returns (
      fun       varchar(50) NOT NULL,
      jid       varchar(255) NOT NULL,
      return    text NOT NULL,
      full_ret  text,
      id        varchar(255) NOT NULL,
      success   varchar(10) NOT NULL,
      alter_time   TIMESTAMP WITH TIME ZONE DEFAULT now()
    );

    CREATE INDEX idx_salt_returns_id ON salt_returns (id);
    CREATE INDEX idx_salt_returns_jid ON salt_returns (jid);
    CREATE INDEX idx_salt_returns_fun ON salt_returns (fun);
    CREATE INDEX idx_salt_returns_updated ON salt_returns (alter_time);

    --
    -- Table structure for table `salt_events`
    --

    DROP TABLE IF EXISTS salt_events;
    DROP SEQUENCE IF EXISTS seq_salt_events_id;
    CREATE SEQUENCE seq_salt_events_id;
    CREATE TABLE salt_events (
        id BIGINT NOT NULL UNIQUE DEFAULT nextval('seq_salt_events_id'),
        tag varchar(255) NOT NULL,
        data text NOT NULL,
        alter_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        master_id varchar(255) NOT NULL
    );

    CREATE INDEX idx_salt_events_tag on salt_events (tag);

    EOF

Required python modules: psycopg2

To use the postgres returner, append '--return postgres' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return postgres

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return postgres --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return postgres --return_kwargs '{"db": "another-salt"}'

"""

import logging
import sys
from contextlib import contextmanager

import salt.exceptions
import salt.returners
import salt.utils.data
import salt.utils.json

try:
    import psycopg2

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

__virtualname__ = "postgres"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_POSTGRES:
        return False, "Could not import postgres returner; psycopg2 is not installed."
    return __virtualname__


def _get_options(ret=None):
    """
    Get the postgres options from salt.
    """
    defaults = {
        "host": "localhost",
        "user": "salt",
        "passwd": "salt",
        "db": "salt",
        "port": 5432,
    }

    attrs = {
        "host": "host",
        "user": "user",
        "passwd": "passwd",
        "db": "db",
        "port": "port",
    }

    _options = salt.returners.get_returner_options(
        "returner.{}".format(__virtualname__),
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
        conn = psycopg2.connect(
            host=_options.get("host"),
            user=_options.get("user"),
            password=_options.get("passwd"),
            database=_options.get("db"),
            port=_options.get("port"),
        )

    except psycopg2.OperationalError as exc:
        raise salt.exceptions.SaltMasterError(
            "postgres returner could not connect to database: {exc}".format(exc=exc)
        )

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
    Return data to a postgres server
    """
    try:
        with _get_serv(ret, commit=True) as cur:
            sql = """INSERT INTO salt_returns
                    (fun, jid, return, id, success, full_ret)
                    VALUES (%s, %s, %s, %s, %s, %s)"""
            cleaned_return = salt.utils.data.decode(ret)
            cur.execute(
                sql,
                (
                    ret["fun"],
                    ret["jid"],
                    salt.utils.json.dumps(cleaned_return["return"]),
                    ret["id"],
                    ret.get("success", False),
                    salt.utils.json.dumps(cleaned_return),
                ),
            )
    except salt.exceptions.SaltMasterError:
        log.critical(
            "Could not store return with postgres returner. PostgreSQL server"
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
            sql = """INSERT INTO salt_events (tag, data, master_id)
                     VALUES (%s, %s, %s)"""
            cur.execute(sql, (tag, salt.utils.json.dumps(data), __opts__["id"]))


def save_load(jid, load, minions=None):  # pylint: disable=unused-argument
    """
    Save the load to the specified jid id
    """
    with _get_serv(commit=True) as cur:

        sql = """INSERT INTO jids
               (jid, load)
                VALUES (%s, %s)"""

        json_data = salt.utils.json.dumps(salt.utils.data.decode(load))
        try:
            cur.execute(sql, (jid, json_data))
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
            return salt.utils.json.loads(data[0])
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
                ret[minion] = salt.utils.json.loads(full_ret)
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
                ret[minion] = salt.utils.json.loads(full_ret)
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
            ret[jid] = salt.utils.jid.format_jid_instance(
                jid, salt.utils.json.loads(load)
            )
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
