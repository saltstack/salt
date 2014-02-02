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


class merger(object):
    result = None
    focus = None
    field_names = None
    num_fields = 0
    depth = 0
    as_list = False

    def __init__(self):
        self.result = self.focus = {}

    def extract_queries(self, args, kwargs):
        # Please note the function signature is NOT an error.  Neither args, nor
        # kwargs should have asterisks.  We are passing in a list and dict,
        # rather than receiving variable args.  Adding asterisks WILL BREAK the
        # function completely.

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

        return qbuffer

    def enter_root(self, root):
        # There is no collision protection on root name isolation
        if (root):
            self.result[root] = self.focus = {}
        else:
            self.focus = self.result

    def process_fields(self, field_names, depth):
        # List of field names in correct order.
        self.field_names = field_names
        # number of fields.
        self.num_fields = len(field_names)
        # Constrain depth.
        if (depth == 0) or (depth >= self.num_fields):
            self.depth = self.num_fields - 1
        else:
            self.depth = depth

    def process_results(self, rows):
        for ret in rows:
            # crd is the Current Return Data level, to make this non-recursive.
            crd = self.focus
            # Walk and create dicts above the final layer
            for i in range(0, self.depth-1):
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
                        if self.as_list:
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
            if self.depth == self.num_fields - 1:
                nk = self.num_fields-2
                # Should we and will we have a list at the end?
                if self.as_list and (ret[nk] in crd):
                    temp = crd[ret[nk]]
                    if (type(temp) is list):
                        # Already list, append
                        temp.append(ret[self.num_fields-1])
                    else:
                        # Convert to list
                        crd[ret[nk]] = [temp, ret[self.num_fields-1]]
                else:
                    # No clobber checks then
                    crd[ret[nk]] = ret[self.num_fields-1]
            else:
                # Otherwise, the field name is the key but we have a spare.
                # The spare results because of {c: d} vs {"c": c, "d": d }
                # So, make that last dict
                if ret[self.depth-1] not in crd:
                    crd[ret[self.depth-1]] = {}
                crd = crd[ret[self.depth-1]]
                # Now for the remaining keys, we put them in to the dict
                for i in range(self.depth, self.num_fields):
                    nk = self.field_names[i]
                    # Collision detection
                    if self.as_list and (nk in crd):
                        # Same as before...
                        if (type(crd[nk]) is list):
                            crd[nk].append(ret[i])
                        else:
                            crd[nk] = [crd[nk], ret[i]]
                    else:
                        crd[nk] = ret[i]


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
    # For each of those items we process, it depends on the object type:
    # - Strings are executed as is and the pillar depth is determined by the
    #   number of fields returned.
    # - A list has the first entry used as the query, the second as the pillar
    #   depth.
    # - A mapping uses the keys "query" and "depth" as the tuple
    #
    # The depth defines how the dicts are constructed.
    # Essentially if you query for fields a,b,c,d for each row you'll get:
    # - With depth 1: {a: {"b": b, "c": c, "d": d}}
    # - With depth 2: {a: {b: {"c": c, "d": d}}}
    # - With depth 3: {a: {b: {c: d}}}
    # Depth greater than 3 wouldn't be different from 3 itself.
    # Depth of 0 translates to the largest depth needed, so 3 in this case.
    # (max depth == key count - 1)
    # The legacy compatibility translates to depth 1.
    # Then they are merged the in a similar way to plain pillar data, in the
    # order returned by MySQL.
    # Thus subsequent results overwrite previous ones when they collide.
    # If you specify `as_list: True` in the mapping expression it will convert
    # collisions to lists.
    #
    # Finally, if you use pass the queries in via a mapping, the key will be the
    # first level name where as passing them in as a list will place them in the
    # root.  This isolates the query results in to their own subtrees.
    # This may be a help or hindrance to your aims and can be used as such.
    #
    # I want to have it able to generate lists as well as mappings but I've not
    # quite figured how to express that cleanly in the config.
    # Might be something to have it convert a particular field in to a list
    # (for k,v in map: list.append(v))
    # The right most value is easy enough, since it's just a matter of having it
    # make a list instead of overwriting, but inner values are trickier

    # Most of the heavy lifting is in this class for ease of testing.
    return_data = merger()
    qbuffer = return_data.extract_queries(args, kwargs)
    with _get_serv() as cur:
        for root, details in qbuffer.items():
            try:
                # Run the query
                cur.execute(details['query'], (minion_id,))

                # Extract the field names MySQL has returned and process them
                # All heavy lifting is done in the merger class to decouple the
                # logic from MySQL.  Makes it easier to test.
                return_data.process_fields([row[0] for row in cur.description],
                                           details['depth'])
                return_data.enter_root(root)
                return_data.as_list = details['as_list']
                return_data.process_results(cur.fetchall())

                log.debug('ext_pillar MySQL: Return data: {0}'.format(
                          return_data))
            except:
                pass
    return return_data
