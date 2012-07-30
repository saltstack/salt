================
Network Topology
================

Salt is based on a powerful, asynchronous, network topology using ZeroMQ. Many
ZeroMQ systems are in place to emable communication. The central idea is have
the fastest communication possible.

Servers
=======

The Salt Master runs 2 network services. First is the ZeroMQ PUB system. This
service by default runs on port ``4505`` and can be configured via the
``publish_port`` option in the master configuration.

Second is the ZeroMQ REP system. This is a seperate interface used for all
bi-directional communication with minions. By default this system binds to
port ``4506`` and can be configured via the ``ret_port`` option in the master.

PUB/SUB
=======

The commands sent out via the salt client are broadcast out to the minions via
ZeroMQ PUB/SUB. This is done by allowing the minions to maintain a connection
back to the Salt Master and then all connecions are informed to download the
command data at once. The command data is kept extreamly small (usually less
than 1K) so it is bnto a burden on the network.

Return
======

The PUB/SUB system is a one way communication, so once a publish is sent out
the PUB interface on the master has not future communication with the minion.
The minion after running the command then sends the command's return data back
to the master via the ``ret_port``.
