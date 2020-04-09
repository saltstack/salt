# -*- coding: utf-8 -*-
"""
Use a postgresql server for the master job cache. This helps the job cache to
cope with scale.

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

:maintainer:    gjredelinghuys@gmail.com
:maturity:      Stable
:depends:       psycopg2
:platform:      all

To enable this returner the minion will need the psycopg2 installed and
the following values configured in the master config:

.. code-block:: yaml

    master_job_cache: postgres_local_cache
    master_job_cache.postgres.host: 'salt'
    master_job_cache.postgres.user: 'salt'
    master_job_cache.postgres.passwd: 'salt'
    master_job_cache.postgres.db: 'salt'
    master_job_cache.postgres.port: 5432

Running the following command as the postgres user should create the database
correctly:

.. code-block:: sql

    psql << EOF
    CREATE ROLE salt WITH PASSWORD 'salt';
    CREATE DATABASE salt WITH OWNER salt;
    EOF

In case the postgres database is a remote host, you'll need this command also:

.. code-block:: sql

   ALTER ROLE salt WITH LOGIN;

and then:

.. code-block:: sql

    psql -h localhost -U salt << EOF
    --
    -- Table structure for table 'jids'
    --

    DROP TABLE IF EXISTS jids;
    CREATE TABLE jids (
      jid   varchar(20) PRIMARY KEY,
      started TIMESTAMP WITH TIME ZONE DEFAULT now(),
      tgt_type text NOT NULL,
      cmd text NOT NULL,
      tgt text NOT NULL,
      kwargs text NOT NULL,
      ret text NOT NULL,
      username text NOT NULL,
      arg text NOT NULL,
      fun text NOT NULL
    );

    --
    -- Table structure for table 'salt_returns'
    --
    -- note that 'success' must not have NOT NULL constraint, since
    -- some functions don't provide it.

    DROP TABLE IF EXISTS salt_returns;
    CREATE TABLE salt_returns (
      added     TIMESTAMP WITH TIME ZONE DEFAULT now(),
      fun       text NOT NULL,
      jid       varchar(20) NOT NULL,
      return    text NOT NULL,
      id        text NOT NULL,
      success   boolean
    );
    CREATE INDEX ON salt_returns (added);
    CREATE INDEX ON salt_returns (id);
    CREATE INDEX ON salt_returns (jid);
    CREATE INDEX ON salt_returns (fun);

    DROP TABLE IF EXISTS salt_events;
    CREATE TABLE salt_events (
      id SERIAL,
      tag text NOT NULL,
      data text NOT NULL,
      alter_time TIMESTAMP WITH TIME ZONE DEFAULT now(),
      master_id text NOT NULL
    );
    CREATE INDEX ON salt_events (tag);
    CREATE INDEX ON salt_events (data);
    CREATE INDEX ON salt_events (id);
    CREATE INDEX ON salt_events (master_id);
    EOF

Required python modules: psycopg2
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import re
import sys

# Import salt libs
import salt.utils.jid
import salt.utils.json
from salt.ext import six

# Import third party libs
try:
    import psycopg2

    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

log = logging.getLogger(__name__)

__virtualname__ = "postgres_local_cache"


def __virtual__():
    if not HAS_POSTGRES:
        return (False, "Could not import psycopg2; postges_local_cache disabled")
    return __virtualname__


def _get_conn():
    """
    Return a postgres connection.
    """
    try:
        conn = psycopg2.connect(
            host=__opts__["master_job_cache.postgres.host"],
            user=__opts__["master_job_cache.postgres.user"],
            password=__opts__["master_job_cache.postgres.passwd"],
            database=__opts__["master_job_cache.postgres.db"],
            port=__opts__["master_job_cache.postgres.port"],
        )
    except psycopg2.OperationalError:
        log.error("Could not connect to SQL server: %s", sys.exc_info()[0])
        return None
    return conn


def _close_conn(conn):
    """
    Close the postgres connection.
    """
    conn.commit()
    conn.close()


def _format_job_instance(job):
    """
    Format the job instance correctly
    """
    ret = {
        "Function": job.get("fun", "unknown-function"),
        "Arguments": salt.utils.json.loads(job.get("arg", "[]")),
        # unlikely but safeguard from invalid returns
        "Target": job.get("tgt", "unknown-target"),
        "Target-type": job.get("tgt_type", "list"),
        "User": job.get("user", "root"),
    }
    # TODO: Add Metadata support when it is merged from develop
    return ret


def _format_jid_instance(jid, job):
    """
    Format the jid correctly
    """
    ret = _format_job_instance(job)
    ret.update({"StartTime": salt.utils.jid.jid_to_time(jid)})
    return ret


def _gen_jid(cur):
    """
    Generate an unique job id
    """
    jid = salt.utils.jid.gen_jid(__opts__)
    sql = """SELECT jid FROM jids WHERE jid = %s"""
    cur.execute(sql, (jid,))
    data = cur.fetchall()
    if not data:
        return jid
    return None


def prep_jid(nocache=False, passed_jid=None):
    """
    Return a job id and prepare the job id directory
    This is the function responsible for making sure jids don't collide
    (unless its passed a jid). So do what you have to do to make sure that
    stays the case
    """
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    if passed_jid is None:
        jid = _gen_jid(cur)
    else:
        jid = passed_jid
    while not jid:
        log.info("jid clash, generating a new one")
        jid = _gen_jid(cur)

    cur.close()
    conn.close()
    return jid


def returner(load):
    """
    Return data to a postgres server
    """
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    sql = """INSERT INTO salt_returns
            (fun, jid, return, id, success)
            VALUES (%s, %s, %s, %s, %s)"""
    job_ret = {
        "return": six.text_type(six.text_type(load["return"]), "utf-8", "replace")
    }
    if "retcode" in load:
        job_ret["retcode"] = load["retcode"]
    if "success" in load:
        job_ret["success"] = load["success"]
    cur.execute(
        sql,
        (
            load["fun"],
            load["jid"],
            salt.utils.json.dumps(job_ret),
            load["id"],
            load.get("success"),
        ),
    )
    _close_conn(conn)


def event_return(events):
    """
    Return event to a postgres server

    Require that configuration be enabled via 'event_return'
    option in master config.
    """
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    for event in events:
        tag = event.get("tag", "")
        data = event.get("data", "")
        sql = """INSERT INTO salt_events
                (tag, data, master_id)
                VALUES (%s, %s, %s)"""
        cur.execute(sql, (tag, salt.utils.json.dumps(data), __opts__["id"]))
    _close_conn(conn)


def save_load(jid, clear_load, minions=None):
    """
    Save the load to the specified jid id
    """
    jid = _escape_jid(jid)
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    sql = (
        """INSERT INTO jids """
        """(jid, started, tgt_type, cmd, tgt, kwargs, ret, username, arg,"""
        """ fun) """
        """VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    )

    cur.execute(
        sql,
        (
            jid,
            salt.utils.jid.jid_to_time(jid),
            six.text_type(clear_load.get("tgt_type")),
            six.text_type(clear_load.get("cmd")),
            six.text_type(clear_load.get("tgt")),
            six.text_type(clear_load.get("kwargs")),
            six.text_type(clear_load.get("ret")),
            six.text_type(clear_load.get("user")),
            six.text_type(salt.utils.json.dumps(clear_load.get("arg"))),
            six.text_type(clear_load.get("fun")),
        ),
    )
    # TODO: Add Metadata support when it is merged from develop
    _close_conn(conn)


def save_minions(jid, minions, syndic_id=None):  # pylint: disable=unused-argument
    """
    Included for API consistency
    """


def _escape_jid(jid):
    """
    Do proper formatting of the jid
    """
    jid = six.text_type(jid)
    jid = re.sub(r"'*", "", jid)
    return jid


def _build_dict(data):
    """
    Rebuild dict
    """
    result = {}
    # TODO: Add Metadata support when it is merged from develop
    result["jid"] = data[0]
    result["tgt_type"] = data[1]
    result["cmd"] = data[2]
    result["tgt"] = data[3]
    result["kwargs"] = data[4]
    result["ret"] = data[5]
    result["user"] = data[6]
    result["arg"] = data[7]
    result["fun"] = data[8]
    return result


def get_load(jid):
    """
    Return the load data that marks a specified jid
    """
    jid = _escape_jid(jid)
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    sql = (
        """SELECT jid, tgt_type, cmd, tgt, kwargs, ret, username, arg,"""
        """ fun FROM jids WHERE jid = %s"""
    )
    cur.execute(sql, (jid,))
    data = cur.fetchone()
    if data:
        return _build_dict(data)
    _close_conn(conn)
    return {}


def get_jid(jid):
    """
    Return the information returned when the specified job id was executed
    """
    jid = _escape_jid(jid)
    conn = _get_conn()
    if conn is None:
        return None
    cur = conn.cursor()
    sql = """SELECT id, return FROM salt_returns WHERE jid = %s"""

    cur.execute(sql, (jid,))
    data = cur.fetchall()
    ret = {}
    if data:
        for minion, full_ret in data:
            ret_data = salt.utils.json.loads(full_ret)
            if not isinstance(ret_data, dict) or "return" not in ret_data:
                # Convert the old format in which the return contains the only return data to the
                # new that is dict containing 'return' and optionally 'retcode' and 'success'.
                ret_data = {"return": ret_data}
            ret[minion] = ret_data
    _close_conn(conn)
    return ret


def get_jids():
    """
    Return a list of all job ids
    For master job cache this also formats the output and returns a string
    """
    conn = _get_conn()
    cur = conn.cursor()
    sql = (
        """SELECT """
        """jid, tgt_type, cmd, tgt, kwargs, ret, username, arg, fun """
        """FROM jids"""
    )
    if __opts__["keep_jobs"] != 0:
        sql = (
            sql
            + " WHERE started > NOW() - INTERVAL '"
            + six.text_type(__opts__["keep_jobs"])
            + "' HOUR"
        )

    cur.execute(sql)
    ret = {}
    data = cur.fetchone()
    while data:
        data_dict = _build_dict(data)
        ret[data_dict["jid"]] = _format_jid_instance(data_dict["jid"], data_dict)
        data = cur.fetchone()
    cur.close()
    conn.close()
    return ret


def clean_old_jobs():
    """
    Clean out the old jobs from the job cache
    """
    return
