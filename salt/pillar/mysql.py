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

# Please don't strip redundant parentheses from this file.
# I have added some for clarity.

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

def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Execute queries, merge and return as a dict
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
# Depth greater than 3 wouldn't be different from 3 itself.
# Depth of 0 translates to the largest depth needed, so 3 in this case. key count - 1.
# The legacy compatibility translates to depth 1.
# Then they are merged the same way normal pillar data is, in the order returned by MySQL.
# Thus subsequent results overwrite previous ones when they collide.
# If you specify `as_list: True` in the mapping expression it will convert collisions to lists.
#
# Finally, if you use pass the queries in via a mapping, the key will be the first level name
# where as passing them in as a list will place them in the root.  This isolates the query results, including in how the lists are built.
# This may be a help or hindrance to your aims and can be used as such.
#
# I want to have it able to generate lists as well as mappings but I've not quite figured how to express that cleanly in the config.
# Might be something to have it convert a particular field in to a list (for k,v in map: list.append(v))
# The right most value is easy enough, since it's just a matter of having it make a list instead of overwriting, but inner values are trickier

    # First, this is the query buffer.  Contains lists of [base,sql]
    qbuffer = []

    # Is there an old style mysql_query?
    if 'mysql_query' in kwargs:
        qbuffer.append([None, kwargs.pop('mysql_query')])

    # Add on the non-keywords...
    qbuffer.extend([[None, s] for s in args])

    # And then the keywords...
    # They aren't in definition order, but they can't conflict each other.
    qbuffer.extend([[k, v] for k, v in kwargs.items()])

    # Filter out values that don't have queries.
    qbuffer = filter(
        lambda x: (
            (type(x) is str and len(x)) or
            ((type(x) in (list, dict)) and (len(x) > 0) and x[0]) or
            (type(x) is dict and 'query' in x)
        ),
        qbuffer)

    # Next, turn the whole buffer in to full dicts.
    for qb in qbuffer:
        defaults = {'query': '',
                    'depth': 0,
                    'as_list': False
                   }
        if type(qb[1]) is str:
            defaults['query'] = qb[1]
        elif type(qb[1]) in (list, tuple):
            defaults['query'] = qb[1][0]
            if len(qb[1]) == 1:
                defaults['depth'] = qb[1][1]
            # May set 'as_list' from qb[1][2].
        else:
            defaults.update(qb[1])
        qb[1] = defaults

    return_data = {}
    with _get_serv() as cur:
        for root, details in qbuffer.items():
            try:
                # Run the query
                cur.execute(details['query'], (minion_id,))
                # Extract the field names MySQL has returned.
                field_names = [row[0] for row in cur.description]
                # And number of fields.
                num_fields = len(field_names)
                # Constrain depth.
                depth = details['depth']
                if (depth == 0) or (depth >= num_fields):
                    depth = num_fields - 1

                # There is no collision protection on root name isolation
                if (root):
                    return_data_root = {}
                    return_data[root] = return_data_root
                else:
                    return_data_root = return_data

                for ret in cur.fetchall():
                    # crd is the Current Return Data level, to make this non-recursive.
                    crd = return_data_root
                    # Walk and create dicts above the final layer
                    for i in range(0,depth-1):
                        if (ret[i] not in crd):
                            # Key missing
                            crd[ret[i]] = {}
                        else:
                            # Check type of collision
                            ty = type(crd[ret[i]])
                            if (ty is list):
                                # Already made list
                                temp = {}
                                crd[ret[i]].append(temp)
                                crd = temp
                            elif (ty is not dict):
                                # Not a list, not a dict
                                if (details['as_list']):
                                    # Make list
                                    temp = {}
                                    crd[ret[i]] = [crd[ret[i]], temp]
                                    crd = temp
                                else:
                                    # Overwrite
                                    crd = crd[ret[i]] = {}
                            else:
                                # dict, descend.
                                crd = crd[ret[i]]

                    # If this test is true, the penultimate field is the key
                    if depth == num_fields - 1:
                        # Should we and will we have a list at the end?
                        if details['as_list'] and (ret[num_fields-2] in crd):
                            temp = crd[ret[num_fields-2]]
                            if (type(temp) is list):
                                # Already list, append
                                temp.append(ret[num_fields-1])
                            else:
                                # Convert to list
                                crd[ret[num_fields-2]] = [temp, ret[num_fields-1]]
                        else:
                            # No clobber checks then
                            crd[ret[num_fields-2]] = ret[num_fields-1]
                    else:
                        # Otherwise, the field name is the key but we have a spare.
                        # The spare results because of {c: d} vs {"c": c, "d": d }
                        # So, make that last dict
                        if ret[depth-1] not in crd:
                            crd[ret[depth-1]] = {}
                        crd = crd[ret[depth-1]]
                        # Now for the remaining keys, we put them in to the dict
                        for i in range(depth, num_fields):
                            # Collision detection
                            if details['as_list'] and (field_names[i] in crd):
                                # Same as before...
                                if (type(crd[field_names[i]]) is list):
                                    crd[field_names[i]].append(ret[i])
                                else:
                                    crd[field_names[i]] = [crd[field_names[i]], ret[i]]
                            else:
                                crd[field_names[i]] = ret[i]

                log.debug('ext_pillar MySQL: Return data: {0}'.format(return_data))
            except:
                pass
    return return_data
