'''
Return data to a mysql server

To enable this returner the minion will need the python client for mysql
installed and the following values configured in the minion or master
config, these are the defaults:

    mysql.host: 'salt'
    mysql.user: 'salt'
    mysql.passwd: 'salt'
    mysql.db: 'salt'
    mysql.port: 3306
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
        
        # Add minion to minion list
        #sql2 = '''INSERT IGNORE INTO `salt`.`minions`
                #(`id`) VALUES (%s)'''
        #cur.execute(sql2, (ret['id'],))

        # Add jid to jid list
        #sql3 = '''INSERT IGNORE INTO `salt`.`jids`
                #(`jid`) VALUES (%s)'''
        #cur.execute(sql3, (ret['jid'],))


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
                WHERE `jid` = '%s';'''
        
        cur.execute(sql, (jid,))
        data = cur.fetchone()
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
        sql = '''SELECT id, fun, jid
                FROM `salt_returns`
                WHERE `fun` = %s
                AND `jid` IN (SELECT MAX(`jid`) 
                FROM `salt_returns` GROUP BY `id`, `fun`)'''
        
        cur.execute(sql, (fun,))
        data = cur.fetchall()

        ret = {}
        if data:
            for minion, full_ret in data:
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
        return cur.fetchall()


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
        return cur.fetchall()
