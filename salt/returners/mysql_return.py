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
                (`fun`, `jid`, `return`, `id`, `success`, `full_ret' )
                VALUES (%s, %s, %s, %s, %s)''' #json.dumps(ret))

        cur.execute(sql, (ret['fun'], ret['jid'], ret['return'], ret['id'], 
                            ret['success'], json.dumps(ret)))
        #serv.lpush('{0}:{1}'.format(ret['id'], ret['fun']), ret['jid'])

        sql2 = '''INSERT IGNORE INTO `salt`.`minions`
                (`id`) VALUES (%s)'''

        cur.execute(sql2, (ret['id'],))

        #serv.sadd('minions', ret['id'])


def save_load(jid, load):
    '''
    Save the load to the speified jib id
    '''
    serv = _get_serv()
    serv.set(jid, json.dumps(load))


def get_load(jid):
    '''
    Return the load data that marks a specified jid
    '''
    serv = _get_serv()
    data = serv.get(jid)
    if data:
        return json.loads(data)
    return {}


def get_jid(jid):
    '''
    Return the information returned when the specified job id was executed
    '''
    serv = _get_serv()
    ret = {}
    for minion in serv.smembers('minions'):
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = json.loads(data)
    return ret

def get_fun(fun):
    '''
    Return a dict of the last function called for all minions
    '''
    serv = _get_serv()
    ret = {}
    for minion in serv.smembers('minions'):
        ind_str = '{0}:{1}'.format(minion, fun)
        try:
            jid = serv.lindex(ind_str, 0)
        except Exception:
            continue
        data = serv.get('{0}:{1}'.format(minion, jid))
        if data:
            ret[minion] = json.loads(data)
    return ret
