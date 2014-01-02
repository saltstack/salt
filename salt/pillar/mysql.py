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

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

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
# this is pretty much WIP still, not sure whether this is a parameter that is being filled in at some point.
#    log.debug('ext_pillar MySQL args: {0}'.format(args))
#    log.debug('ext_pillar MySQL kwargs: {0}'.format(kwargs))
#
#    if len(pillar) == 1:
#        log.debug('Pillar set, updating query to include it.')
#        mysql_query += ' AND pillar={0}'.format(pillar)
#        # @todo handle multiple pillars in case its requested, instead of returning everything we have for the minion
#

    with _get_serv() as cur:
        cur.execute(mysql_query, (minion_id,))

        return_data = {}
        for ret in cur.fetchall():
            return_data[ret[0]] = ret[1]

        log.debug('ext_pillar MySQL: Return data: {0}'.format(return_data))
        return return_data
