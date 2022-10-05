.. _salt_architecture:

Overview
========

In its most typical use, Salt is a software application in which clients,
called "minions" can be commanded and controlled from a central command server
called a "master".

Commands are normally issued to the minions (via the master) by calling a
client script simply called, 'salt'.

Salt features a pluggable transport system to issue commands from a master to
minions. The default transport is ZeroMQ.

Salt Client
===========

Overview
--------

The salt client is run on the same machine as the Salt Master and communicates
with the salt-master to issue commands and to receive the results and display
them to the user.

The primary abstraction for the salt client is called 'LocalClient'.

When LocalClient wants to publish a command to minions, it connects to the
master by issuing a request to the master's ReqServer (TCP: 4506)

The LocalClient system listens to responses for its requests by listening to
the master event bus publisher (master_event_pub.ipc).

Salt Master
===========

Overview
--------

The salt-master daemon runs on the designated Salt master and performs
functions such as authenticating minions, sending, and receiving requests
from connected minions and sending and receiving requests and replies to the
'salt' CLI.

Moving Pieces
-------------

When a Salt master starts up, a number of processes are started, all of which
are called 'salt-master' in a process-list but have various role categories.

Among those categories are:

    * Publisher
    * EventPublisher
    * MWorker

Publisher
---------

The Publisher process is responsible for sending commands over the designated
transport to connected minions. The Publisher is bound to the following:

    * TCP: port 4505
    * IPC: publish_pull.ipc

Each salt minion establishes a connection to the master Publisher.

EventPublisher
--------------

The EventPublisher publishes master events out to any event listeners. It is
bound to the following:

    * IPC: master_event_pull.ipc
    * IPC: master_event_pub.ipc

MWorker
-------

Worker processes manage the back-end operations for the Salt Master.

The number of workers is equivalent to the number of 'worker_threads'
specified in the master configuration and is always at least one.

Workers are bound to the following:

    * IPC: workers.ipc

ReqServer
---------

The Salt request server takes requests and distributes them to available MWorker
processes for processing. It also receives replies back from minions.

The ReqServer is bound to the following:
    * TCP: 4506
    * IPC: workers.ipc

Each salt minion establishes a connection to the master ReqServer.


Job Flow
--------

The Salt master works by always publishing commands to all connected minions
and the minions decide if the command is meant for them by checking themselves
against the command target.

The typical lifecycle of a salt job from the perspective of the master
might be as follows:

1) A command is issued on the CLI. For example, 'salt my_minion test.version'.

2) The 'salt' command uses LocalClient to generate a request to the salt master
   by connecting to the ReqServer on TCP:4506 and issuing the job.

3) The salt-master ReqServer sees the request and passes it to an available
   MWorker over workers.ipc.

4) A worker picks up the request and handles it. First, it checks to ensure
   that the requested user has permissions to issue the command. Then, it sends
   the publish command to all connected minions. For the curious, this happens
   in ClearFuncs.publish().

5) The worker announces on the master event bus that it is about to publish a
   job to connected minions. This happens by placing the event on the master
   event bus (master_event_pull.ipc) where the EventPublisher picks it up and
   distributes it to all connected event listeners on master_event_pub.ipc.

6) The message to the minions is encrypted and sent to the Publisher via IPC on
   publish_pull.ipc.

7) Connected minions have a TCP session established with the Publisher on TCP
   port 4505 where they await commands. When the Publisher receives the job
   over publish_pull, it sends the jobs across the wire to the minions for
   processing.

8) After the minions receive the request, they decrypt it and perform any
   requested work, if they determine that they are targeted to do so.

9) When the minion is ready to respond, it publishes the result of its job back
   to the master by sending the encrypted result back to the master on TCP 4506
   where it is again picked up by the ReqServer and forwarded to an available
   MWorker for processing. (Again, this happens by passing this message across
   workers.ipc to an available worker.)

10) When the MWorker receives the job it decrypts it and fires an event onto
    the master event bus (master_event_pull.ipc). (Again for the curious, this
    happens in AESFuncs._return().

11) The EventPublisher sees this event and re-publishes it on the bus to all
    connected listeners of the master event bus (on master_event_pub.ipc). This
    is where the LocalClient has been waiting, listening to the event bus for
    minion replies. It gathers the job and stores the result.

12) When all targeted minions have replied or the timeout has been exceeded,
    the salt client displays the results of the job to the user on the CLI.

Salt Minion
===========

Overview
--------

The salt-minion is a single process that sits on machines to be managed by
Salt. It can either operate as a stand-alone daemon which accepts commands
locally via 'salt-call' or it can connect back to a master and receive commands
remotely.

When starting up, salt minions connect *back* to a master defined in the minion
config file. They connect to two ports on the master:

    * TCP: 4505
        This is the connection to the master Publisher. It is on this port that
        the minion receives jobs from the master.

    * TCP: 4506
        This is the connection to the master ReqServer. It is on this port that
        the minion sends job results back to the master.


Event System
------------

Similar to the master, a salt-minion has its own event system that operates
over IPC by default. The minion event system operates on a push/pull system
with IPC files at minion_event_<unique_id>_pub.ipc and
minion_event_<unique_id>_pull.ipc.

The astute reader might ask why have an event bus at all with a single-process
daemon. The answer is that the salt-minion may fork other processes as required
to do the work without blocking the main salt-minion process and this
necessitates a mechanism by which those processes can communicate with each
other. Secondarily, this provides a bus by which any user with sufficient
permissions can read or write to the bus as a common interface with the salt
minion.


Minion Job Flow
---------------

When a salt minion starts up, it attempts to connect to the Publisher and the
ReqServer on the salt master. It then attempts to authenticate and once the
minion has successfully authenticated, it simply listens for jobs.

Jobs normally come either come from the 'salt-call' script run by a local user
on the salt minion or they can come directly from a master.

The job flow on a minion, coming from the master via a 'salt' command is as
follows:

1) A master publishes a job that is received by a minion as outlined by the
master's job flow above.
2) The minion is polling its receive socket that's connected to the master
Publisher (TCP 4505 on master). When it detects an incoming message, it picks it
up from the socket and decrypts it.
3) A new minion process or thread is created and provided with the contents of the
decrypted message. The _thread_return() method is provided with the contents of
the received message.
4) The new minion thread is created. The _thread_return() function starts up
and actually calls out to the requested function contained in the job.
5) The requested function runs and returns a result. [Still in thread.]
6) The result of the function that's run is published on the minion's local event bus with event
tag "__master_req_channel_payload" [Still in thread.]
7) Thread exits. Because the main thread was only blocked for the time that it
took to initialize the worker thread, many other requests could have been
received and processed during this time.
8) Minion event handler gets the event with tag "__master_req_channel_payload"
and sends the payload to master's ReqServer (TCP 4506 on master), via the long-running async request channel
that was opened when minion first started up.



A Note on ClearFuncs vs. AESFuncs
=================================

A common source of confusion is determining when messages are passed in the
clear and when they are passed using encryption. There are two rules governing
this behaviour:

1) ClearFuncs is used for intra-master communication and during the initial
authentication handshake between a minion and master during the key exchange.
2) AESFuncs is used everywhere else.
