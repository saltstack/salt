# -*- coding: utf-8 -*-
'''
Retrieve Pillar data by doing a MySQL query

:maturity: new
:depends: python-mysqldb
:platform: all

Theory of mysql ext_pillar
=====================================

Ok, here's the theory for how this works...

- If there's a keyword arg of mysql_query, that'll go first.
- Then any non-keyword args are processed in order.
- Finally, remaining keywords are processed.

We do this so that it's backward compatible with older configs.
Keyword arguments are sorted before being appended, so that they're predictable,
but they will always be applied last so overall it's moot.

For each of those items we process, it depends on the object type:

- Strings are executed as is and the pillar depth is determined by the number
  of fields returned.
- A list has the first entry used as the query, the second as the pillar depth.
- A mapping uses the keys "query" and "depth" as the tuple

You can retrieve as many fields as you like, how the get used depends on the
exact settings.

Configuring the mysql ext_pillar
=====================================

First an example of how legacy queries were specified.

.. code-block:: yaml

  ext_pillar:
    - mysql:
        mysql_query: "SELECT pillar,value FROM pillars WHERE minion_id = %s"

Alternatively, a list of queries can be passed in

.. code-block:: yaml

  ext_pillar:
    - mysql:
        - "SELECT pillar,value FROM pillars WHERE minion_id = %s"
        - "SELECT pillar,value FROM more_pillars WHERE minion_id = %s"

Or you can pass in a mapping

.. code-block:: yaml

  ext_pillar:
    - mysql:
        main: "SELECT pillar,value FROM pillars WHERE minion_id = %s"
        extras: "SELECT pillar,value FROM more_pillars WHERE minion_id = %s"

The query can be provided as a string as we have just shown, but they can be
provided as lists

.. code-block:: yaml

  ext_pillar:
    - mysql:
        - "SELECT pillar,value FROM pillars WHERE minion_id = %s"
          2

Or as a mapping

.. code-block:: yaml

  ext_pillar:
    - mysql:
        - query: "SELECT pillar,value FROM pillars WHERE minion_id = %s"
          depth: 2

The depth defines how the dicts are constructed.
Essentially if you query for fields a,b,c,d for each row you'll get:

- With depth 1: {a: {"b": b, "c": c, "d": d}}
- With depth 2: {a: {b: {"c": c, "d": d}}}
- With depth 3: {a: {b: {c: d}}}

Depth greater than 3 wouldn't be different from 3 itself.
Depth of 0 translates to the largest depth needed, so 3 in this case.
(max depth == key count - 1)

The legacy compatibility translates to depth 1.

Then they are merged the in a similar way to plain pillar data, in the order
returned by MySQL.

Thus subsequent results overwrite previous ones when they collide.

If you specify `as_list: True` in the mapping expression it will convert
collisions to lists.

If you specify `with_lists: '...'` in the mapping expression it will
convert the specified depths to list.  The string provided is a sequence
numbers that are comma separated.  The string '1,3' will result in::

    a,b,c,d,e,1  # field 1 same, field 3 differs
    a,b,c,f,g,2  # ^^^^
    a,z,h,y,j,3  # field 1 same, field 3 same
    a,z,h,y,k,4  # ^^^^
      ^   ^

These columns define list grouping

.. code-block:: python

    {a: [
          {c: [
              {e: 1},
              {g: 2}
              ]
          },
          {h: [
              {j: 3, k: 4 }
              ]
          }
    ]}

The range for with_lists is 1 to number_of_fields, inclusive.
Numbers outside this range are ignored.

Finally, if you use pass the queries in via a mapping, the key will be the
first level name where as passing them in as a list will place them in the
root.  This isolates the query results in to their own subtrees.
This may be a help or hindrance to your aims and can be used as such.

You can basically use any SELECT query that gets you the information, you
could even do joins or subqueries in case your minion_id is stored elsewhere.
It is capable of handling single rows or multiple rows per minion.

MySQL configuration of the MySQL returner is being used (mysql.db, mysql.user,
mysql.pass, mysql.port, mysql.host)

Required python modules: MySQLdb

More complete example
=====================================

.. code-block:: yaml

    mysql:
      user: 'salt'
      pass: 'super_secret_password'
      db: 'salt_db'

    ext_pillar:
      - mysql:
          fromdb:
            query: 'SELECT col1,col2,col3,col4,col5,col6,col7
                      FROM some_random_table
                     WHERE minion_pattern LIKE %s'
            depth: 5
            as_list: True
            with_lists: [1,3]
'''

# Please don't strip redundant parentheses from this file.
# I have added some for clarity.

# tests/unit/pillar/mysql_test.py may help understand this code.

# Import python libs
from contextlib import contextmanager
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict

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
    return True


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
    _opts = __opts__.get('mysql', {})
    for attr in defaults:
        if attr not in _opts:
            log.debug('Using default for MySQL {0}'.format(attr))
            _options[attr] = defaults[attr]
            continue
        _options[attr] = _opts[attr]
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
    '''
        This class receives and processes the database rows in a database
        agnostic way.
    '''
    result = None
    focus = None
    field_names = None
    num_fields = 0
    depth = 0
    as_list = False
    with_lists = None

    def __init__(self):
        self.result = self.focus = {}

    def extract_queries(self, args, kwargs):
        '''
            This function normalizes the config block in to a set of queries we
            can use.  The return is a list of consistently laid out dicts.
        '''
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
        klist = kwargs.keys()
        klist.sort()
        qbuffer.extend([[k, kwargs[k]] for k in klist])

        # Filter out values that don't have queries.
        qbuffer = filter(
            lambda x: (
                (type(x[1]) is str and len(x[1]))
                or
                ((type(x[1]) in (list, tuple)) and (len(x[1]) > 0) and x[1][0])
                or
                (type(x[1]) is dict and 'query' in x[1] and len(x[1]['query']))
            ),
            qbuffer)

        # Next, turn the whole buffer in to full dicts.
        for qb in qbuffer:
            defaults = {'query': '',
                        'depth': 0,
                        'as_list': False,
                        'with_lists': None
                        }
            if type(qb[1]) is str:
                defaults['query'] = qb[1]
            elif type(qb[1]) in (list, tuple):
                defaults['query'] = qb[1][0]
                if len(qb[1]) > 1:
                    defaults['depth'] = qb[1][1]
                # May set 'as_list' from qb[1][2].
            else:
                defaults.update(qb[1])
                if defaults['with_lists']:
                    defaults['with_lists'] = [
                        int(i) for i in defaults['with_lists'].split(',')
                    ]
            qb[1] = defaults

        return qbuffer

    def enter_root(self, root):
        '''
            Set self.focus for kwarg queries
        '''
        # There is no collision protection on root name isolation
        if root:
            self.result[root] = self.focus = {}
        else:
            self.focus = self.result

    def process_fields(self, field_names, depth):
        '''
            The primary purpose of this function is to store the sql field list
            and the depth to which we process.
        '''
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
        '''
            This function takes a list of database results and iterates over,
            merging them in to a dict form.
        '''
        listify = OrderedDict()
        listify_dicts = OrderedDict()
        for ret in rows:
            # crd is the Current Return Data level, to make this non-recursive.
            crd = self.focus
            # Walk and create dicts above the final layer
            for i in range(0, self.depth-1):
                # At the end we'll use listify to find values to make a list of
                if i+1 in self.with_lists:
                    if id(crd) not in listify:
                        listify[id(crd)] = []
                        listify_dicts[id(crd)] = crd
                    if ret[i] not in listify[id(crd)]:
                        listify[id(crd)].append(ret[i])
                if ret[i] not in crd:
                    # Key missing
                    crd[ret[i]] = {}
                    crd = crd[ret[i]]
                else:
                    # Check type of collision
                    ty = type(crd[ret[i]])
                    if ty is list:
                        # Already made list
                        temp = {}
                        crd[ret[i]].append(temp)
                        crd = temp
                    elif ty is not dict:
                        # Not a list, not a dict
                        if self.as_list:
                            # Make list
                            temp = {}
                            crd[ret[i]] = [crd[ret[i]], temp]
                            crd = temp
                        else:
                            # Overwrite
                            crd[ret[i]] = {}
                            crd = crd[ret[i]]
                    else:
                        # dict, descend.
                        crd = crd[ret[i]]

            # If this test is true, the penultimate field is the key
            if self.depth == self.num_fields - 1:
                nk = self.num_fields-2  # Aka, self.depth-1
                # Should we and will we have a list at the end?
                if ((self.as_list and (ret[nk] in crd)) or
                        (nk+1 in self.with_lists)):
                    if ret[nk] in crd:
                        if type(crd[ret[nk]]) is not list:
                            crd[ret[nk]] = [crd[ret[nk]]]
                        # if it's already a list, do nothing
                    else:
                        crd[ret[nk]] = []
                    crd[ret[nk]].append(ret[self.num_fields-1])
                else:
                    # No clobber checks then
                    crd[ret[nk]] = ret[self.num_fields-1]
            else:
                # Otherwise, the field name is the key but we have a spare.
                # The spare results because of {c: d} vs {c: {"d": d, "e": e }}
                # So, make that last dict
                if ret[self.depth-1] not in crd:
                    crd[ret[self.depth-1]] = {}
                # This bit doesn't escape listify
                if self.depth in self.with_lists:
                    if id(crd) not in listify:
                        listify[id(crd)] = []
                        listify_dicts[id(crd)] = crd
                    if ret[self.depth-1] not in listify[id(crd)]:
                        listify[id(crd)].append(ret[self.depth-1])
                crd = crd[ret[self.depth-1]]
                # Now for the remaining keys, we put them in to the dict
                for i in range(self.depth, self.num_fields):
                    nk = self.field_names[i]
                    # Listify
                    if i+1 in self.with_lists:
                        if id(crd) not in listify:
                            listify[id(crd)] = []
                            listify_dicts[id(crd)] = crd
                        if nk not in listify[id(crd)]:
                            listify[id(crd)].append(nk)
                    # Collision detection
                    if self.as_list and (nk in crd):
                        # Same as before...
                        if type(crd[nk]) is list:
                            crd[nk].append(ret[i])
                        else:
                            crd[nk] = [crd[nk], ret[i]]
                    else:
                        crd[nk] = ret[i]
        # Get key list and work backwards.  This is inner-out processing
        ks = listify_dicts.keys()
        ks.reverse()
        for i in ks:
            d = listify_dicts[i]
            for k in listify[i]:
                if type(d[k]) is dict:
                    d[k] = d[k].values()
                elif type(d[k]) is not list:
                    d[k] = [d[k]]


def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Execute queries, merge and return as a dict
    '''
    log.info('Querying MySQL for information for {0}'.format(minion_id, ))
    #
    #    log.debug('ext_pillar MySQL args: {0}'.format(args))
    #    log.debug('ext_pillar MySQL kwargs: {0}'.format(kwargs))
    #
    # Most of the heavy lifting is in this class for ease of testing.
    return_data = merger()
    qbuffer = return_data.extract_queries(args, kwargs)
    with _get_serv() as cur:
        for root, details in qbuffer:
            # Run the query
            cur.execute(details['query'], (minion_id,))

            # Extract the field names MySQL has returned and process them
            # All heavy lifting is done in the merger class to decouple the
            # logic from MySQL.  Makes it easier to test.
            return_data.process_fields([row[0] for row in cur.description],
                                       details['depth'])
            return_data.enter_root(root)
            return_data.as_list = details['as_list']
            if details['with_lists']:
                return_data.with_lists = details['with_lists']
            else:
                return_data.with_lists = []
            return_data.process_results(cur.fetchall())

            log.debug('ext_pillar MySQL: Return data: {0}'.format(
                      return_data))
    return return_data.result
