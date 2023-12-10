.. _transports:

==============
Salt Transport
==============


Transports in Salt are used by :ref:`Channels <channels>` to send messages between Masters, Minions,
and the Salt CLI. Transports can be brokerless or brokered. There are two types
of server / client implementations needed to implement a channel.


Publish Server
==============

The publish server implements a publish / subscribe paradigm and is used by
Minions to receive jobs from Masters.

Publish Client
==============

The publish client subscribes to, and receives messages from a Publish Server.


Request Server
==============

The request server implements a request / reply paradigm. Every request sent by
the client must receive exactly one reply.

Request Client
==============

The request client sends requests to a Request Server and receives a reply message.


.. toctree::

    zeromq
    tcp
