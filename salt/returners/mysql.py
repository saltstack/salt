"""
Return data to a mysql server

:maintainer:    Dave Boucha <dave@saltstack.com>, Seth House <shouse@saltstack.com>
:maturity:      mature
:depends:       python-mysqldb
:platform:      all

To enable this returner, the minion will need the python client for mysql
installed and the following values configured in the minion or master
config. These are the defaults:

.. code-block:: yaml

    mysql.host: 'salt'
    mysql.user: 'salt'
    mysql.pass: 'salt'
    mysql.db: 'salt'
    mysql.port: 3306

SSL is optional. The defaults are set to None. If you do not want to use SSL,
either exclude these options or set them to None.

.. code-block:: yaml

    mysql.ssl_ca: None
    mysql.ssl_cert: None
    mysql.ssl_key: None

Alternative configuration values can be used by prefacing the configuration
with `alternative.`. Any values not found in the alternative configuration will
be pulled from the default location. As stated above, SSL configuration is
optional. The following ssl options are simply for illustration purposes:

.. code-block:: yaml

    alternative.mysql.host: 'salt'
    alternative.mysql.user: 'salt'
    alternative.mysql.pass: 'salt'
    alternative.mysql.db: 'salt'
    alternative.mysql.port: 3306
    alternative.mysql.ssl_ca: '/etc/pki/mysql/certs/localhost.pem'
    alternative.mysql.ssl_cert: '/etc/pki/mysql/certs/localhost.crt'
    alternative.mysql.ssl_key: '/etc/pki/mysql/certs/localhost.key'

Should you wish the returner data to be cleaned out every so often, set
`keep_jobs_seconds` to the number of hours for the jobs to live in the
tables.  Setting it to `0` will cause the data to stay in the tables. The
default setting for `keep_jobs_seconds` is set to `86400`.

Should you wish to archive jobs in a different table for later processing,
set `archive_jobs` to True.  Salt will create 3 archive tables

- `jids_archive`
- `salt_returns_archive`
- `salt_events_archive`

and move the contents of `jids`, `salt_returns`, and `salt_events` that are
more than `keep_jobs_seconds` seconds old to these tables.

Use the following mysql database schema:

.. code-block:: sql

    CREATE DATABASE  `salt`
      DEFAULT CHARACTER SET utf8
      DEFAULT COLLATE utf8_general_ci;

    USE `salt`;

    --
    -- Table structure for table `jids`
    --

    DROP TABLE IF EXISTS `jids`;
    CREATE TABLE `jids` (
      `jid` varchar(255) NOT NULL,
      `load` mediumtext NOT NULL,
      UNIQUE KEY `jid` (`jid`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

    --
    -- Table structure for table `salt_returns`
    --

    DROP TABLE IF EXISTS `salt_returns`;
    CREATE TABLE `salt_returns` (
      `fun` varchar(50) NOT NULL,
      `jid` varchar(255) NOT NULL,
      `return` mediumtext NOT NULL,
      `id` varchar(255) NOT NULL,
      `success` varchar(10) NOT NULL,
      `full_ret` mediumtext NOT NULL,
      `alter_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      KEY `id` (`id`),
      KEY `jid` (`jid`),
      KEY `fun` (`fun`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

    --
    -- Table structure for table `salt_events`
    --

    DROP TABLE IF EXISTS `salt_events`;
    CREATE TABLE `salt_events` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `tag` varchar(255) NOT NULL,
    `data` mediumtext NOT NULL,
    `alter_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `master_id` varchar(255) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `tag` (`tag`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

Required python modules: MySQLdb

To use the mysql returner, append '--return mysql' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return mysql

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return mysql --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return mysql --return_kwargs '{"db": "another-salt"}'

"""

import logging
import sys
from contextlib import contextmanager

import salt.exceptions
import salt.returners
import salt.utils.data
import salt.utils.job
import salt.utils.json

try:
    # Trying to import MySQLdb
    import MySQLdb
    import MySQLdb.converters
    import MySQLdb.cursors
    from MySQLdb.connections import OperationalError
except ImportError:
    try:
        # MySQLdb import failed, try to import PyMySQL
        import pymysql

        pymysql.install_as_MySQLdb()
        import MySQLdb
        import MySQLdb.converters
        import MySQLdb.cursors
        from MySQLdb.err import OperationalError
    except ImportError:
        MySQLdb = None

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "mysql"


def __virtual__():
    """
    Confirm that a python mysql client is installed.
    """
    return bool(MySQLdb), "No python mysql client installed." if MySQLdb is None else ""


def _get_options(ret=None):
    """
    Returns options used for the MySQL connection.
    """
    defaults = {
        "host": "salt",
        "user": "salt",
        "pass": "salt",
        "db": "salt",
        "port": 3306,
        "ssl_ca": None,
        "ssl_cert": None,
        "ssl_key": None,
    }

    attrs = {
        "host": "host",
        "user": "user",
        "pass": "pass",
        "db": "db",
        "port": "port",
        "ssl_ca": "ssl_ca",
        "ssl_cert": "ssl_cert",
        "ssl_key": "ssl_key",
    }

    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults,
    )
    # post processing
    for k, v in _options.items():
        if isinstance(v, str) and v.lower() == "none":
            # Ensure 'None' is rendered as None
            _options[k] = None
        if k == "port":
            # Ensure port is an int
            _options[k] = int(v)

    return _options


@contextmanager
def _get_serv(ret=None, commit=False):
    """
    Return a mysql cursor
    """
    _options = _get_options(ret)

    connect = True
    if __context__ and "mysql_returner_conn" in __context__:
        try:
            log.debug("Trying to reuse MySQL connection pool")
            conn = __context__["mysql_returner_conn"]
            conn.ping()
            connect = False
        except OperationalError as exc:
            log.debug("OperationalError on ping: %s", exc)

    if connect:
        log.debug("Generating new MySQL connection pool")
        try:
            # An empty ssl_options dictionary passed to MySQLdb.connect will
            # effectively connect w/o SSL.
            ssl_options = {}
            if _options.get("ssl_ca"):
                ssl_options["ca"] = _options.get("ssl_ca")
            if _options.get("ssl_cert"):
                ssl_options["cert"] = _options.get("ssl_cert")
            if _options.get("ssl_key"):
                ssl_options["key"] = _options.get("ssl_key")
            conn = MySQLdb.connect(
                host=_options.get("host"),
                user=_options.get("user"),
                passwd=_options.get("pass"),
                db=_options.get("db"),
                port=_options.get("port"),
                ssl=ssl_options,
            )

            try:
                __context__["mysql_returner_conn"] = conn
            except TypeError:
                pass
        except OperationalError as exc:
            raise salt.exceptions.SaltMasterError(
                f"MySQL returner could not connect to database: {exc}"
            )

    cursor = conn.cursor()

    try:
        yield cursor
    except MySQLdb.DatabaseError as err:
        error = err.args
        sys.stderr.write(str(error))
        cursor.execute("ROLLBACK")
        raise
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")


def returner(ret):
    """
    Return data to a mysql server
    """
    # if a minion is returning a standalone job, get a jobid
    if ret["jid"] == "req":
        ret["jid"] = prep_jid(nocache=ret.get("nocache", False))
        save_load(ret["jid"], ret)

    try:
        with _get_serv(ret, commit=True) as cur:
            sql = """INSERT INTO `salt_returns`
                     (`fun`, `jid`, `return`, `id`, `success`, `full_ret`)
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
    except salt.exceptions.SaltMasterError as exc:
        log.critical(exc)
        log.critical(
            "Could not store return with MySQL returner. MySQL server unavailable."
        )


def event_return(events):
    """
    Return event to mysql server

    Requires that configuration be enabled via 'event_return'
    option in master config.
    """
    with _get_serv(events, commit=True) as cur:
        for event in events:
            tag = event.get("tag", "")
            data = event.get("data", "")
            sql = """INSERT INTO `salt_events` (`tag`, `data`, `master_id`)
                     VALUES (%s, %s, %s)"""
            cur.execute(sql, (tag, salt.utils.json.dumps(data), __opts__["id"]))


def save_load(jid, load, minions=None):
    """
    Save the load to the specified jid id
    """
    with _get_serv(commit=True) as cur:

        sql = """INSERT INTO `jids` (`jid`, `load`) VALUES (%s, %s)"""

        json_data = salt.utils.json.dumps(salt.utils.data.decode(load))
        try:
            cur.execute(sql, (jid, json_data))
        except MySQLdb.IntegrityError:
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

        sql = """SELECT `load` FROM `jids` WHERE `jid` = %s;"""
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

        sql = """SELECT id, full_ret FROM `salt_returns`
                WHERE `jid` = %s"""

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
                FROM `salt_returns` s
                JOIN ( SELECT MAX(`jid`) as jid
                    from `salt_returns` GROUP BY fun, id) max
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

        sql = """SELECT DISTINCT `jid`, `load`
                FROM `jids`"""

        cur.execute(sql)
        data = cur.fetchall()
        ret = {}
        for jid in data:
            ret[jid[0]] = salt.utils.jid.format_jid_instance(
                jid[0], salt.utils.json.loads(jid[1])
            )
        return ret


def get_jids_filter(count, filter_find_job=True):
    """
    Return a list of all job ids
    :param int count: show not more than the count of most recent jobs
    :param bool filter_find_jobs: filter out 'saltutil.find_job' jobs
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT * FROM (
                     SELECT DISTINCT `jid` ,`load` FROM `jids`
                     {0}
                     ORDER BY `jid` DESC limit {1}
                     ) `tmp`
                 ORDER BY `jid`;"""
        where = """WHERE `load` NOT LIKE '%"fun": "saltutil.find_job"%' """

        cur.execute(sql.format(where if filter_find_job else "", count))
        data = cur.fetchall()
        ret = []
        for jid in data:
            ret.append(
                salt.utils.jid.format_jid_instance_ext(
                    jid[0], salt.utils.json.loads(jid[1])
                )
            )
        return ret


def get_minions():
    """
    Return a list of minions
    """
    with _get_serv(ret=None, commit=True) as cur:

        sql = """SELECT DISTINCT id
                FROM `salt_returns`"""

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
    with _get_serv() as cur:
        try:
            sql = (
                "delete from `jids` where jid in (select distinct jid from salt_returns"
                " where alter_time < %s)"
            )
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to delete contents of table 'jids'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))

        try:
            sql = "delete from `salt_returns` where alter_time < %s"
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to delete contents of table"
                " 'salt_returns'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))

        try:
            sql = "delete from `salt_events` where alter_time < %s"
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to delete contents of table"
                " 'salt_events'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))

    return True


def _archive_jobs(timestamp):
    """
    Copy rows to a set of backup tables, then purge rows.
    :param timestamp: Archive rows older than this timestamp
    :return:
    """
    source_tables = ["jids", "salt_returns", "salt_events"]

    with _get_serv() as cur:
        target_tables = {}
        for table_name in source_tables:
            try:
                tmp_table_name = table_name + "_archive"
                sql = "create table if not exists {} like {}".format(
                    tmp_table_name, table_name
                )
                cur.execute(sql)
                cur.execute("COMMIT")
                target_tables[table_name] = tmp_table_name
            except MySQLdb.Error as e:
                log.error(
                    "mysql returner archiver was unable to create the archive tables."
                )
                log.error(str(e))
                raise salt.exceptions.SaltRunnerError(str(e))

        try:
            sql = (
                "insert into `{}` select * from `{}` where jid in (select distinct jid"
                " from salt_returns where alter_time < %s)".format(
                    target_tables["jids"], "jids"
                )
            )
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to copy contents of table 'jids'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))
        except Exception as e:  # pylint: disable=broad-except
            log.error(e)
            raise

        try:
            sql = "insert into `{}` select * from `{}` where alter_time < %s".format(
                target_tables["salt_returns"], "salt_returns"
            )
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to copy contents of table"
                " 'salt_returns'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))

        try:
            sql = "insert into `{}` select * from `{}` where alter_time < %s".format(
                target_tables["salt_events"], "salt_events"
            )
            cur.execute(sql, (timestamp,))
            cur.execute("COMMIT")
        except MySQLdb.Error as e:
            log.error(
                "mysql returner archiver was unable to copy contents of table"
                " 'salt_events'"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))

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
                sql = "select date_sub(now(), interval {} second) as stamp;".format(
                    keep_jobs_seconds
                )
                cur.execute(sql)
                rows = cur.fetchall()
                stamp = rows[0][0]

            if __opts__.get("archive_jobs", False):
                _archive_jobs(stamp)
            else:
                _purge_jobs(stamp)
        except MySQLdb.Error as e:
            log.error(
                "Mysql returner was unable to get timestamp for purge/archive of jobs"
            )
            log.error(str(e))
            raise salt.exceptions.SaltRunnerError(str(e))
