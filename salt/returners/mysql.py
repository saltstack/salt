'''
Return data to a mysql server

To enable this returner the minion will need the python client for mysql
installed and the following values configured in the minion or master
config, these are the defaults::

    mysql.host: 'salt'
    mysql.user: 'salt'
    mysql.passwd: 'salt'
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
      `load` varchar(65000) NOT NULL,
      UNIQUE KEY `jid` (`jid`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

    --
    -- Table structure for table `salt_returns`
    --

    DROP TABLE IF EXISTS `salt_returns`;
    CREATE TABLE `salt_returns` (
      `fun` varchar(50) NOT NULL,
      `jid` varchar(200) NOT NULL,
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
import json

try:
    import MySQLdb 
    has_mysql = True
except ImportError:
    has_mysql = False


def __virtual__():
    if not has_mysql:
        return False
    return 'mysql'


def _get_serv():
    '''
    Return a mysql cursor
    '''
    return MySQLdb.connect(
            host=__salt__['config.option']('mysql.host'),
            user=__salt__['config.option']('mysql.user'),
            passwd=__salt__['config.option']('mysql.passwd'),
            db=__salt__['config.option']('mysql.db'),
            port=__salt__['config.option']('mysql.port'))


def returner(ret):
    '''
    Return data to a mysql server
    '''
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
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
    serv = _get_serv()
    with serv:
        
        cur = serv.cursor()
        sql = '''INSERT INTO `salt`.`jids`
               (`jid`, `load`)
                VALUES (%s, %s)'''

        cur.execute(sql, (jid, json.dumps(load)))


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
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
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
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
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
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
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
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
    serv = _get_serv()
    with serv:

        cur = serv.cursor()
        sql = '''SELECT DISTINCT id 
                FROM `salt`.`salt_returns`'''

        cur.execute(sql)
        data = cur.fetchall()
        ret = []
        for minion in data:
            ret.append(minion[0])
        return ret
