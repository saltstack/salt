.. _returners:

=========
Returners
=========

By default the return values of the commands sent to the Salt minions are
returned to the Salt master, however anything at all can be done with the results
data.

By using a Salt returner, results data can be redirected to external data-stores
for analysis and archival.

Returners pull their configuration values from the Salt minions. Returners are only
configured once, which is generally at load time.

The returner interface allows the return data to be sent to any system that
can receive data. This means that return data can be sent to a Redis server,
a MongoDB server, a MySQL server, or any system.

.. seealso:: :ref:`Full list of builtin returners <all-salt.returners>`

Using Returners
===============

All Salt commands will return the command data back to the master. Specifying
returners will ensure that the data is _also_ sent to the specified returner
interfaces.

Specifying what returners to use is done when the command is invoked:

.. code-block:: bash

    salt '*' test.version --return redis_return

This command will ensure that the redis_return returner is used.

It is also possible to specify multiple returners:

.. code-block:: bash

    salt '*' test.version --return mongo_return,redis_return,cassandra_return

In this scenario all three returners will be called and the data from the
test.version command will be sent out to the three named returners.

Writing a Returner
==================

Returners are Salt modules that allow the redirection of results data to targets other than the Salt Master.

Returners Are Easy To Write!
----------------------------

Writing a Salt returner is straightforward.

A returner is a Python module containing at minimum a ``returner`` function.
Other optional functions can be included to add support for
:conf_master:`master_job_cache`, :ref:`external-job-cache`, and `Event Returners`_.

``returner``
    The ``returner`` function must accept a single argument. The argument
    contains return data from the called minion function. If the minion
    function ``test.version`` is called, the value of the argument will be a
    dictionary. Run the following command from a Salt master to get a sample
    of the dictionary:

.. code-block:: bash

    salt-call --local --metadata test.version --out=pprint

.. code-block:: python

    import redis
    import salt.utils.json

    def returner(ret):
        '''
        Return information to a redis server
        '''
        # Get a redis connection
        serv = redis.Redis(
            host='redis-serv.example.com',
            port=6379,
            db='0')
        serv.sadd("%(id)s:jobs" % ret, ret['jid'])
        serv.set("%(jid)s:%(id)s" % ret, salt.utils.json.dumps(ret['return']))
        serv.sadd('jobs', ret['jid'])
        serv.sadd(ret['jid'], ret['id'])

The above example of a returner set to send the data to a Redis server
serializes the data as JSON and sets it in redis.

Using Custom Returner Modules
-----------------------------

Place custom returners in a ``_returners/`` directory within the
:conf_master:`file_roots` specified by the master config file.

Custom returners are distributed when any of the following are called:

- :mod:`state.apply <salt.modules.state.apply_>`
- :mod:`saltutil.sync_returners <salt.modules.saltutil.sync_returners>`
- :mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>`

Any custom returners which have been synced to a minion that are named the
same as one of Salt's default set of returners will take the place of the
default returner with the same name.

Naming the Returner
-------------------

Note that a returner's default name is its filename (i.e. ``foo.py`` becomes
returner ``foo``), but that its name can be overridden by using a
:ref:`__virtual__ function <virtual-modules>`. A good example of this can be
found in the `redis`_ returner, which is named ``redis_return.py`` but is
loaded as simply ``redis``:

.. code-block:: python

    try:
        import redis
        HAS_REDIS = True
    except ImportError:
        HAS_REDIS = False

    __virtualname__ = 'redis'

    def __virtual__():
        if not HAS_REDIS:
            return False
        return __virtualname__

Master Job Cache Support
------------------------

:conf_master:`master_job_cache`, :ref:`external-job-cache`, and `Event Returners`_.
Salt's :conf_master:`master_job_cache` allows returners to be used as a pluggable
replacement for the :ref:`default_job_cache`. In order to do so, a returner
must implement the following functions:

.. note::

    The code samples contained in this section were taken from the cassandra_cql
    returner.

``prep_jid``
    Ensures that job ids (jid) don't collide, unless passed_jid is provided.

    ``nocache`` is an optional boolean that indicates if return data
    should be cached. ``passed_jid`` is a caller provided jid which should be
    returned unconditionally.

.. code-block:: python

    def prep_jid(nocache, passed_jid=None):  # pylint: disable=unused-argument
        '''
        Do any work necessary to prepare a JID, including sending a custom id
        '''
        return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()

``save_load``
    Save job information.  The ``jid`` is generated by ``prep_jid`` and should
    be considered a unique identifier for the job. The jid, for example, could
    be used as the primary/unique key in a database. The ``load`` is what is
    returned to a Salt master by a minion. ``minions`` is a list of minions
    that the job was run against. The following code example stores the load as
    a JSON string in the salt.jids table.

.. code-block:: python

    import salt.utils.json

    def save_load(jid, load, minions=None):
        '''
        Save the load to the specified jid id
        '''
        query = '''INSERT INTO salt.jids (
                     jid, load
                   ) VALUES (
                     '{0}', '{1}'
                   );'''.format(jid, salt.utils.json.dumps(load))

        # cassandra_cql.cql_query may raise a CommandExecutionError
        try:
            __salt__['cassandra_cql.cql_query'](query)
        except CommandExecutionError:
            log.critical('Could not save load in jids table.')
            raise
        except Exception as e:
            log.critical(
                'Unexpected error while inserting into jids: {0}'.format(e)
            )
            raise


``get_load``
    must accept a job id (jid) and return the job load stored by ``save_load``,
    or an empty dictionary when not found.

.. code-block:: python

    def get_load(jid):
        '''
        Return the load data that marks a specified jid
        '''
        query = '''SELECT load FROM salt.jids WHERE jid = '{0}';'''.format(jid)

        ret = {}

        # cassandra_cql.cql_query may raise a CommandExecutionError
        try:
            data = __salt__['cassandra_cql.cql_query'](query)
            if data:
                load = data[0].get('load')
                if load:
                    ret = json.loads(load)
        except CommandExecutionError:
            log.critical('Could not get load from jids table.')
            raise
        except Exception as e:
            log.critical('''Unexpected error while getting load from
             jids: {0}'''.format(str(e)))
            raise

        return ret


External Job Cache Support
--------------------------

Salt's :ref:`external-job-cache` extends the :conf_master:`master_job_cache`. External
Job Cache support requires the following functions in addition to what is
required for Master Job Cache support:

``get_jid``
    Return a dictionary containing the information (load) returned by each
    minion when the specified job id was executed.

Sample:

.. code-block:: JSON

   {
       "local": {
           "master_minion": {
               "fun_args": [],
               "jid": "20150330121011408195",
               "return": "2018.3.4",
               "retcode": 0,
               "success": true,
               "cmd": "_return",
               "_stamp": "2015-03-30T12:10:12.708663",
               "fun": "test.version",
               "id": "master_minion"
           }
       }
   }

``get_fun``
    Return a dictionary of minions that called a given Salt function as their
    last function call.

Sample:

.. code-block:: JSON

   {
       "local": {
           "minion1": "test.version",
           "minion3": "test.version",
           "minion2": "test.version"
       }
   }

``get_jids``
    Return a list of all job ids.

Sample:

.. code-block:: JSON

    {
        "local": [
            "20150330121011408195",
            "20150330195922139916"
        ]
    }

``get_minions``
    Returns a list of minions

Sample:

.. code-block:: JSON

   {
        "local": [
            "minion3",
            "minion2",
            "minion1",
            "master_minion"
        ]
   }

Please refer to one or more of the existing returners (i.e. mysql,
cassandra_cql) if you need further clarification.


Event Support
-------------

An ``event_return`` function must be added to the returner module to allow
events to be logged from a master via the returner. A list of events are passed
to the function by the master.

The following example was taken from the MySQL returner. In this example, each
event is inserted into the salt_events table keyed on the event tag. The tag
contains the jid and therefore is guaranteed to be unique.

.. code-block:: python

    import salt.utils.json

    def event_return(events):
     '''
     Return event to mysql server

     Requires that configuration be enabled via 'event_return'
     option in master config.
     '''
     with _get_serv(events, commit=True) as cur:
         for event in events:
             tag = event.get('tag', '')
             data = event.get('data', '')
             sql = '''INSERT INTO `salt_events` (`tag`, `data`, `master_id` )
                      VALUES (%s, %s, %s)'''
             cur.execute(sql, (tag, salt.utils.json.dumps(data), __opts__['id']))


Testing the Returner
--------------------

The ``returner``, ``prep_jid``, ``save_load``, ``get_load``, and
``event_return`` functions can be tested by configuring the
:conf_master:`master_job_cache` and `Event Returners`_ in the master config
file and submitting a job to ``test.version`` each minion from the master.

Once you have successfully exercised the Master Job Cache functions, test the
External Job Cache functions using the ``ret`` execution module.

.. code-block:: bash

    salt-call ret.get_jids cassandra_cql --output=json
    salt-call ret.get_fun cassandra_cql test.version --output=json
    salt-call ret.get_minions cassandra_cql --output=json
    salt-call ret.get_jid cassandra_cql 20150330121011408195 --output=json

Event Returners
===============

For maximum visibility into the history of events across a Salt
infrastructure, all events seen by a salt master may be logged to one or
more returners.

To enable event logging, set the ``event_return`` configuration option in the
master config to the returner(s) which should be designated as the handler
for event returns.

.. note::
    Not all returners support event returns. Verify a returner has an
    ``event_return()`` function before using.

.. note::
    On larger installations, many hundreds of events may be generated on a
    busy master every second. Be certain to closely monitor the storage of
    a given returner as Salt can easily overwhelm an underpowered server
    with thousands of returns.

Full List of Returners
======================

.. toctree::
    all/index

.. _`redis`: https://github.com/saltstack/salt/tree/|repo_primary_branch|/salt/returners/redis_return.py
