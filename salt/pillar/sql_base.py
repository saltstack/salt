"""
Retrieve Pillar data by doing a SQL query

This module is not meant to be used directly as an ext_pillar.
It is a place to put code common to PEP 249 compliant SQL database adapters.
It exposes a python ABC that can be subclassed for new database providers.

:maturity: new
:platform: all

Theory of sql_base ext_pillar
=============================

Ok, here's the theory for how this works...

- First, any non-keyword args are processed in order.
- Then, remaining keywords are processed.

We do this so that it's backward compatible with older configs.
Keyword arguments are sorted before being appended, so that they're predictable,
but they will always be applied last so overall it's moot.

For each of those items we process, it depends on the object type:

- Strings are executed as is and the pillar depth is determined by the number
  of fields returned.
- A list has the first entry used as the query, the second as the pillar depth.
- A mapping uses the keys "query" and "depth" as the tuple

You can retrieve as many fields as you like, how they get used depends on the
exact settings.

Configuring a sql_base ext_pillar
=================================

The sql_base ext_pillar cannot be used directly, but shares query configuration
with its implementations. These examples use a fake 'sql_base' adapter, which
should be replaced with the name of the adapter you are using.

A list of queries can be passed in

.. code-block:: yaml

  ext_pillar:
    - sql_base:
        - "SELECT pillar,value FROM pillars WHERE minion_id = %s"
        - "SELECT pillar,value FROM more_pillars WHERE minion_id = %s"

Or you can pass in a mapping

.. code-block:: yaml

  ext_pillar:
    - sql_base:
        main: "SELECT pillar,value FROM pillars WHERE minion_id = %s"
        extras: "SELECT pillar,value FROM more_pillars WHERE minion_id = %s"

The query can be provided as a string as we have just shown, but they can be
provided as lists

.. code-block:: yaml

  ext_pillar:
    - sql_base:
        - "SELECT pillar,value FROM pillars WHERE minion_id = %s"
          2

Or as a mapping

.. code-block:: yaml

  ext_pillar:
    - sql_base:
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

Then they are merged in a similar way to plain pillar data, in the order
returned by the SQL database.

Thus subsequent results overwrite previous ones when they collide.

The ignore_null option can be used to change the overwrite behavior so that
only non-NULL values in subsequent results will overwrite.  This can be used
to selectively overwrite default values.

.. code-block:: yaml

  ext_pillar:
    - sql_base:
        - query: "SELECT pillar,value FROM pillars WHERE minion_id = 'default' and minion_id != %s"
          depth: 2
        - query: "SELECT pillar,value FROM pillars WHERE minion_id = %s"
          depth: 2
          ignore_null: True

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

Finally, if you pass the queries in via a mapping, the key will be the
first level name where as passing them in as a list will place them in the
root.  This isolates the query results into their own subtrees.
This may be a help or hindrance to your aims and can be used as such.

You can basically use any SELECT query that gets you the information, you
could even do joins or subqueries in case your minion_id is stored elsewhere.
It is capable of handling single rows or multiple rows per minion.

Configuration of the connection depends on the adapter in use.

More complete example for MySQL (to also show configuration)
============================================================

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
"""

import abc  # Added in python2.6 so always available
import logging

from salt.utils.odict import OrderedDict

# Please don't strip redundant parentheses from this file.
# I have added some for clarity.

# tests/unit/pillar/mysql_test.py may help understand this code.


# Set up logging
log = logging.getLogger(__name__)


# This ext_pillar is abstract and cannot be used directory
def __virtual__():
    return False


class SqlBaseExtPillar(metaclass=abc.ABCMeta):
    """
    This class receives and processes the database rows in a database
    agnostic way.
    """

    result = None
    focus = None
    field_names = None
    num_fields = 0
    depth = 0
    as_list = False
    with_lists = None
    ignore_null = False

    def __init__(self):
        self.result = self.focus = {}

    @classmethod
    @abc.abstractmethod
    def _db_name(cls):
        """
        Return a friendly name for the database, e.g. 'MySQL' or 'SQLite'.
        Used in logging output.
        """

    @abc.abstractmethod
    def _get_cursor(self):
        """
        Yield a PEP 249 compliant Cursor as a context manager.
        """

    def extract_queries(self, args, kwargs):
        """
        This function normalizes the config block into a set of queries we
        can use.  The return is a list of consistently laid out dicts.
        """
        # Please note the function signature is NOT an error.  Neither args, nor
        # kwargs should have asterisks.  We are passing in a list and dict,
        # rather than receiving variable args.  Adding asterisks WILL BREAK the
        # function completely.

        # First, this is the query buffer.  Contains lists of [base,sql]
        qbuffer = []

        # Add on the non-keywords...
        qbuffer.extend([[None, s] for s in args])

        # And then the keywords...
        # They aren't in definition order, but they can't conflict each other.
        klist = list(kwargs.keys())
        klist.sort()
        qbuffer.extend([[k, kwargs[k]] for k in klist])

        # Filter out values that don't have queries.
        qbuffer = [
            x
            for x in qbuffer
            if (
                (isinstance(x[1], str) and len(x[1]))
                or (isinstance(x[1], (list, tuple)) and (len(x[1]) > 0) and x[1][0])
                or (isinstance(x[1], dict) and "query" in x[1] and len(x[1]["query"]))
            )
        ]

        # Next, turn the whole buffer into full dicts.
        for qb in qbuffer:
            defaults = {
                "query": "",
                "depth": 0,
                "as_list": False,
                "with_lists": None,
                "ignore_null": False,
            }
            if isinstance(qb[1], str):
                defaults["query"] = qb[1]
            elif isinstance(qb[1], (list, tuple)):
                defaults["query"] = qb[1][0]
                if len(qb[1]) > 1:
                    defaults["depth"] = qb[1][1]
                # May set 'as_list' from qb[1][2].
            else:
                defaults.update(qb[1])
                if defaults["with_lists"] and isinstance(defaults["with_lists"], str):
                    defaults["with_lists"] = [
                        int(i) for i in defaults["with_lists"].split(",")
                    ]
            qb[1] = defaults

        return qbuffer

    def enter_root(self, root):
        """
        Set self.focus for kwarg queries
        """
        # There is no collision protection on root name isolation
        if root:
            self.result[root] = self.focus = {}
        else:
            self.focus = self.result

    def process_fields(self, field_names, depth):
        """
        The primary purpose of this function is to store the sql field list
        and the depth to which we process.
        """
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
        """
        This function takes a list of database results and iterates over,
        merging them into a dict form.
        """
        listify = OrderedDict()
        listify_dicts = OrderedDict()
        for ret in rows:
            # crd is the Current Return Data level, to make this non-recursive.
            crd = self.focus
            # Walk and create dicts above the final layer
            for i in range(0, self.depth - 1):
                # At the end we'll use listify to find values to make a list of
                if i + 1 in self.with_lists:
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
                nk = self.num_fields - 2  # Aka, self.depth-1
                # Should we and will we have a list at the end?
                if (self.as_list and (ret[nk] in crd)) or (nk + 1 in self.with_lists):
                    if ret[nk] in crd:
                        if not isinstance(crd[ret[nk]], list):
                            crd[ret[nk]] = [crd[ret[nk]]]
                        # if it's already a list, do nothing
                    else:
                        crd[ret[nk]] = []
                    crd[ret[nk]].append(ret[self.num_fields - 1])
                else:
                    if not self.ignore_null or ret[self.num_fields - 1] is not None:
                        crd[ret[nk]] = ret[self.num_fields - 1]
            else:
                # Otherwise, the field name is the key but we have a spare.
                # The spare results because of {c: d} vs {c: {"d": d, "e": e }}
                # So, make that last dict
                if ret[self.depth - 1] not in crd:
                    crd[ret[self.depth - 1]] = {}
                # This bit doesn't escape listify
                if self.depth in self.with_lists:
                    if id(crd) not in listify:
                        listify[id(crd)] = []
                        listify_dicts[id(crd)] = crd
                    if ret[self.depth - 1] not in listify[id(crd)]:
                        listify[id(crd)].append(ret[self.depth - 1])
                crd = crd[ret[self.depth - 1]]
                # Now for the remaining keys, we put them into the dict
                for i in range(self.depth, self.num_fields):
                    nk = self.field_names[i]
                    # Listify
                    if i + 1 in self.with_lists:
                        if id(crd) not in listify:
                            listify[id(crd)] = []
                            listify_dicts[id(crd)] = crd
                        if nk not in listify[id(crd)]:
                            listify[id(crd)].append(nk)
                    # Collision detection
                    if self.as_list and (nk in crd):
                        # Same as before...
                        if isinstance(crd[nk], list):
                            crd[nk].append(ret[i])
                        else:
                            crd[nk] = [crd[nk], ret[i]]
                    else:
                        if not self.ignore_null or ret[i] is not None:
                            crd[nk] = ret[i]
        # Get key list and work backwards.  This is inner-out processing
        ks = list(listify_dicts.keys())
        ks.reverse()
        for i in ks:
            d = listify_dicts[i]
            for k in listify[i]:
                if isinstance(d[k], dict):
                    d[k] = list(d[k].values())
                elif isinstance(d[k], list):
                    d[k] = [d[k]]

    def fetch(self, minion_id, pillar, *args, **kwargs):  # pylint: disable=W0613
        """
        Execute queries, merge and return as a dict.
        """
        db_name = self._db_name()
        log.info("Querying %s for information for %s", db_name, minion_id)
        #
        #    log.debug('ext_pillar %s args: %s', db_name, args)
        #    log.debug('ext_pillar %s kwargs: %s', db_name, kwargs)
        #
        # Most of the heavy lifting is in this class for ease of testing.
        qbuffer = self.extract_queries(args, kwargs)
        with self._get_cursor() as cursor:
            for root, details in qbuffer:
                # Run the query
                cursor.execute(details["query"], (minion_id,))

                # Extract the field names the db has returned and process them
                self.process_fields(
                    [row[0] for row in cursor.description], details["depth"]
                )
                self.enter_root(root)
                self.as_list = details["as_list"]
                if details["with_lists"]:
                    self.with_lists = details["with_lists"]
                else:
                    self.with_lists = []
                self.ignore_null = details["ignore_null"]
                self.process_results(cursor.fetchall())

                log.debug("ext_pillar %s: Return data: %s", db_name, self)
        return self.result


# To extend this module you must define a top level ext_pillar procedure
# See mysql.py for an example
