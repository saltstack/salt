'''
Return data to a mysql server

:maintainer:    Dave Boucha <dave@saltstack.com>, Seth House <shouse@saltstack.com>
:maturity:      new
:depends:       python-mysqldb
:platform:      all

To enable this returner the minion will need the python client for mysql
installed and the following values configured in the minion or master
config, these are the defaults::

    mysql.host: 'salt'
    mysql.user: 'salt'
    mysql.pass: 'salt'
    mysql.db: 'salt'
    mysql.port: 3306

Use the following mysql database schema::

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
      KEY `id` (`id`),
      KEY `jid` (`jid`),
      KEY `fun` (`fun`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

Required python modules: MySQLdb
'''

# Import python libs
from contextlib import contextmanager
import json, sys

try:
    import MySQLdb 
    has_mysql = True
except ImportError:
    has_mysql = False


def __virtual__():
    if not has_mysql:
        return False
    return 'mysql'

@contextmanager
def _get_serv(commit=False):
    '''
    Return a mysql cursor
    '''
    conn =  MySQLdb.connect(
            host=__salt__['config.option']('mysql.host'),
            user=__salt__['config.option']('mysql.user'),
            passwd=__salt__['config.option']('mysql.pass'),
            db=__salt__['config.option']('mysql.db'),
            port=__salt__['config.option']('mysql.port'),
            )
    cursor = conn.cursor()
    try:
        yield cursor
    except MySQLdb.DatabaseError as err:
        error, = err.args
        sys.stderr.write(error.message)
        cursor.execute("ROLLBACK")
        raise err
    else:
        if commit:
            cursor.execute("COMMIT")
        else:
            cursor.execute("ROLLBACK")
    finally:
        conn.close()


def returner(ret):
    '''
    Return data to a mysql server
    '''
    with _get_serv(commit=True) as cur:

        sql = '''INSERT INTO `salt`.`salt_returns`
                (`fun`, `jid`, `return`, `id`, `success`, `full_ret` )
                VALUES (%s, %s, %s, %s, %s, %s)'''
        cur.execute(sql, (ret['fun'], ret['jid'], 
                            str(ret['return']), ret['id'], 
                            ret['success'], json.dumps(ret)))


def save_load(jid, load):
    '''
    Save the load to the specified jid id
    '''
    with _get_serv(commit=True) as cur:
        
        sql = '''INSERT INTO `salt`.`jids`
               (`jid`, `load`)
                VALUES (%s, %s)'''

        cur.execute(sql, (jid, json.dumps(load)))


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    with _get_serv(commit=True) as cur:

        sql = '''SELECT load FROM `salt`.`jids`
                WHERE `jid` = '%s';'''

        cur.execute(sql, (jid,))
        data = cur.fetchone()
        if data:
            return json.loads(data)
        return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    with _get_serv(commit=True) as cur:

        sql = '''SELECT id, full_ret FROM `salt`.`salt_returns`
                WHERE `jid` = %s'''
        
        cur.execute(sql, (jid,))
        data = cur.fetchall()
        ret = {}
        if data:
            for minion, full_ret in data:
                ret[minion] = json.loads(full_ret)
        return ret


def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    with _get_serv(commit=True) as cur:

        sql = '''SELECT s.id,s.jid, s.full_ret
                FROM `salt`.`salt_returns` s
                JOIN ( SELECT MAX(`jid`) as jid 
                    from `salt`.`salt_returns` GROUP BY fun, id) max
                ON s.jid = max.jid
                WHERE s.fun = %s
                '''
        
        cur.execute(sql, (fun,))
        data = cur.fetchall()

        ret = {}
        if data:
            for minion, jid, full_ret in data:
                ret[minion] = json.loads(full_ret)
        return ret

def get_jids():
    '''
    Return a list of all job ids
    '''
    with _get_serv(commit=True) as cur:

        sql = '''SELECT DISTINCT jid
                FROM `salt`.`jids`'''

        cur.execute(sql)
        data = cur.fetchall()
        ret = []
        for jid in data:
            ret.append(jid[0])
        return ret



def get_minions():
    '''
    Return a list of minions
    '''
    with _get_serv(commit=True) as cur:

        sql = '''SELECT DISTINCT id 
                FROM `salt`.`salt_returns`'''

        cur.execute(sql)
        data = cur.fetchall()
        ret = []
        for minion in data:
            ret.append(minion[0])
        return ret
