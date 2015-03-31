'''
Retrieve Pillar data from the SSE GUI database

:depends: python-mysqldb
'''
from __future__ import absolute_import
import logging
import json

from contextlib import contextmanager

try:
    import MySQLdb
    HAS_MYSQL = True
except:
    HAS_MYSQL = False

log = logging.getLogger(__name__)

@contextmanager
def _get_cursor():
    '''
    Setup the db connection and return the cursor.
    '''
    host = __opts__.get('mysql.host', 'localhost')
    user = __opts__.get('mysql.user', 'salt')
    password = __opts__.get('mysql.pass', 'salt')
    db = __opts__.get('mysql.db', 'salt')
    port = __opts__.get('mysql.port', 3306)

    conn = MySQLdb.connect(host=host,
                           user=user,
                           passwd=password,
                           db=db,
                           port=port)
    cursor = conn.cursor()

    try:
        yield cursor
    except MySQLdb.DatabaseError as err:
        log.exception('Error in ext_pillar SSE: {0}'.format(err.args))
    finally:
        conn.close()


def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Query the db for any pillar data for the given minion id. There are two
    sources that know what pillar goes to what minion:

    - SSE db. Through the target-minion linking table
    - The Master.

    At the time of this writing, we are only ask the SSE db.
    '''
    log.info('Querying SSE DB for pillar data for minion ({0})'.format(minion_id))
    with _get_cursor() as cur:
        sql = """SELECT p.DATA
                    FROM core_pillar AS p,
                        target_target_pillars AS tp,
                        target_targetminions AS tm,
                        minion_minion AS m
                    WHERE p.name = tp.pillar_id
                        AND tp.target_id = tm.target_id
                        AND tm.minion_id = m.id
                        AND m.minion_id = %s"""

        cur.execute(sql, (minion_id))
        updated_pillar = pillar.copy()
        new_pillar_data = cur.fetchall()

        for data in new_pillar_data:
            updated_pillar.update(json.loads(data[0]))

    return updated_pillar
