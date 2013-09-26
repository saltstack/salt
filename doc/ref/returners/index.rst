=========
Returners
=========

By default the return values of the commands sent to the Salt minions are
returned to the salt-master. But since the commands executed on the Salt
minions are detached from the call on the Salt master, anything at all can be
done with the results data.

This is where the returner interface comes in. Returners are modules called
in addition to returning the data to the Salt master.

The returner interface allows the return data to be sent to any system that
can receive data. This means that return data can be sent to a Redis server,
a MongoDB server, a MySQL server, or any system!

.. seealso:: :ref:`Full list of builtin returners <all-salt.returners>`

Using Returners
===============

All commands will return the command data back to the master. Adding more
returners will ensure that the data is also sent to the specified returner
interfaces.

Specifying what returners to use is done when the command is invoked:

.. code-block:: bash

    salt '*' test.ping --return redis_return

This command will ensure that the redis_return returner is used.

It is also possible to specify multiple returners:

.. code-block:: bash

    salt '*' test.ping --return mongo_return,redis_return,cassandra_return

In this scenario all three returners will be called and the data from the
test.ping command will be sent out to the three named returners.

Writing a Returner
==================

A returner is a module which contains a returner function, the returner
function must accept a single argument. this argument is the return data from
the called minion function. So if the minion function ``test.ping`` is called
the value of the argument will be ``True``.

A simple returner is implemented here:

.. code-block:: python

    import redis
    import json

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
        serv.set("%(jid)s:%(id)s" % ret, json.dumps(ret['return']))
        serv.sadd('jobs', ret['jid'])
        serv.sadd(ret['jid'], ret['id'])

This simple example of a returner set to send the data to a redis server
serializes the data as json and sets it in redis.

You can place your custom returners in a ``_returners`` directory within the
:conf_master:`file_roots` specified by the master config file. These custom
returners are distributed when :mod:`state.highstate
<salt.modules.state.highstate>` is run, or by executing the
:mod:`saltutil.sync_returners <salt.modules.saltutil.sync_returners>` or
:mod:`saltutil.sync_all <salt.modules.saltutil.sync_all>` functions.

Any custom returners which have been synced to a minion, that are named the
same as one of Salt's default set of returners, will take the place of the
default returner with the same name. Note that a returner's default name is its
filename (i.e. ``foo.py`` becomes returner ``foo``), but that its name can be
overridden by using a :ref:`__virtual__ function <virtual-modules>`. A good
example of this can be found in the `redis`_ returner, which is named
``redis_return.py`` but is loaded as simply ``redis``:

.. code-block:: python

    try:
        import redis
        HAS_REDIS = True
    except ImportError:
        HAS_REDIS = False

    def __virtual__():
        if not HAS_REDIS:
            return False
        return 'redis'

.. _`redis`: https://github.com/saltstack/salt/blob/develop/salt/returners/redis_return.py

Examples
--------

The collection of built-in Salt returners can be found here:
:blob:`salt/returners`
