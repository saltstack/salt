.. _transports:

==============
Salt Transport
==============


Transports in Salt are used by :ref:`Channels <channels>` to send messages between Masters Minions
and the Salt cli. Transports can be brokerless or brokered. There are two types
of server / client implimentations needed to impliment a channel.


Publish Server
==============

The publish server impliments a publish / subscribe paradigm and is used by
Minions to receive jobs from Masters.

Publish Client
==============

The publish client subscribes and receives messages from a Publish Server.


Request Server
==============

The request server impliments a request / reply paradigm. Every request sent by
the client must recieve exactly one reply.

Request Client
==============

The request client sends requests to a Request Server and recieves a reply message.


.. toctree::

    zeromq
    tcp
