# -*- coding: utf-8 -*-
'''
Retrieve Pillar data by doing a MySQL query

:maturity: new
:depends: python-mysqldb
:platform: all

Configuring the mysql ext_pillar
=====================================
.. code-block:: yaml

  ext_pillar:
    - mysql:
        mysql_query: "SELECT pillar,value FROM pillars WHERE minion_id = %s"

You can basically use any SELECT query here that gets you the information, you
could even do joins or subqueries in case your minion_id is stored elsewhere.
The query should always return two pieces of information in the correct order(
key, value). It is capable of handling single rows or multiple rows per minion.

MySQL configuration of the MySQL returner is being used (mysql.db, mysql.user,
mysql.pass, mysql.port, mysql.host)

Required python modules: MySQLdb
'''

# Import python libs
from contextlib import contextmanager
import logging

# Set up logging
log = logging.getLogger(__name__)

# Import third party libs
try:
    import MySQLdb
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


def __virtual__():
    if not HAS_MYSQL:
        return False
    return 'mysql'


def _get_options():
    '''
    Returns options used for the MySQL connection.
    '''
    defaults = {'host': 'localhost',
                'user': 'salt',
                'pass': 'salt',
                'db': 'salt',
                'port': 3306}
    _options = {}
    for attr in defaults:
        _attr = __salt__['config.option']('mysql.{0}'.format(attr))
        if not _attr:
            log.debug('Using default for MySQL {0}'.format(attr))
            _options[attr] = defaults[attr]
            continue
        _options[attr] = _attr

    return _options


@contextmanager
def _get_serv():
    '''
    Return a mysql cursor
    '''
    _options = _get_options()
    conn = MySQLdb.connect(host=_options['host'],
                           user=_options['user'],
                           passwd=_options['pass'],
                           db=_options['db'], port=_options['port'])
    cursor = conn.cursor()
    try:
        yield cursor
    except MySQLdb.DatabaseError as err:
        log.exception('Error in ext_pillar MySQL: {0}'.format(err.args))
    finally:
        conn.close()


def ext_pillar(minion_id, pillar, mysql_query, *args, **kwargs):
    '''
    Execute the query and return its data as a set
    '''
    log.info('Querying MySQL for information for {0}'.format(minion_id, ))
#
#    log.debug('ext_pillar MySQL args: {0}'.format(args))
#    log.debug('ext_pillar MySQL kwargs: {0}'.format(kwargs))
#
# Ok, here's the plan for how this works...
# - If there's a keyword arg of mysql_query, that'll go first.
# - Then any non-keyworded args are processed in order.
# - Finally, remaining keywords are processed.
# We do this so that it's backward compatible with older configs.
#
# For each of those items we process, it depends on what the object passed in:
# - Strings are executed as is and the pillar depth is determined by the number of fields returned.
# - A list has the first entry used as the query, the second as the pillar depth.
# - A mapping uses the keys "query" and "depth" as the tuple
#
# The depth defines how the dicts are constructed.
# Essentially if you query for fields a,b,c,d for each row you'll get:
# - With depth 1: {a: {"b": b, "c": c, "d": d}}
# - With depth 2: {a: {b: {"c": c, "d": d}}}
# - With depth 3: {a: {b: {c: d}}}
# Then they are merged the same way normal pillar data is, in the order returned by MySQL.
# Thus subsequent results overwrite previous ones when they collide.
# If you specify `list: True` in the mapping expression it will convert collisions to lists.
#
# Finally, if you use pass the queries in via a mapping, the key will be the first level name
# where as passing them in as a list will place them in the root.  This isolates the query results, including in how the lists are built.
# This may be a help or hindrance to your aims and can be used as such.
#
# I want to have it able to generate lists as well as mappings but I've not quite figured how to express that cleanly in the config.
# Might be something to have it convert a particular field in to a list (for k,v in map: list.append(v))
# The right most value is easy enough, since it's just a matter of having it make a list instead of overwriting, but inner values are trickier.
    with _get_serv() as cur:
        cur.execute(mysql_query, (minion_id,))

        return_data = {}
        for ret in cur.fetchall():
            return_data[ret[0]] = ret[1]

        log.debug('ext_pillar MySQL: Return data: {0}'.format(return_data))
        return return_data
