=========
Returners
=========

By default the return values of the commands sent to the salt minions are
returned to the salt-master. But since the commands executed on the salt
minions are detatched from the call on the salt master, there is no need for
the minion to return the data to the salt master.

This is where the returner interface comes in. Returners are modules called
in place of returning the data to the salt master.

The returner interface allows the return data to be sent to any system that
can recieve data. This means that return data can be sent to a Redis server,
a MongoDB server, a MySQL server, or any system!

Full list of builtin returners
==============================

.. toctree::
    :maxdepth: 1
    :glob:

    *

Writing a Returner
==================

A returner is a module which contains a returner function, the returner
function must accept a single argument. this argument is the return data from
the called minion function. So if the minion function ``test.ping`` is called
the value of the argument will be ``True``.

A simple returner is implimented here:

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

The collection of builtin salt returners can be found here:
https://github.com/thatch45/salt/tree/master/salt/returners
