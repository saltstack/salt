=========
Returners
=========

By default the return values of the commands sent to the Salt minions are
returned to the salt-master. But since the commands executed on the Salt
minions are detached from the call on the Salt master, there is no need for
the minion to return the data to the Salt master.

This is where the returner interface comes in. Returners are modules called
in place of returning the data to the Salt master.

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
        # Get a redis commection
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

Examples
--------

The collection of built-in Salt returners can be found here:
:blob:`salt/returners`
