================
ZeroMQ Transport
================

.. note::

    ZeroMQ is the current default transport within Salt

ZeroMQ is a messaging library with bindings into many languages. ZeroMQ implements
a socket interface for message passing, with specific semantics for the socket type.


Publish Server and Client
=========================
The publish server and client are implemented using ZeroMQ's pub/sub sockets. By
default we don't use ZeroMQ's filtering, which means that all publish jobs are
sent to all minions and filtered minion side. ZeroMQ does have publisher side
filtering which can be enabled in salt using :conf_master:`zmq_filtering`.


Request Server and Client
=========================
The request server and client are implemented using ZeroMQ's req/rep sockets.
These sockets enforce a send/recv pattern, which forces salt to serialize
messages through these socket pairs. This means that although the interface is
asynchronous on the minion we cannot send a second message until we have
received the reply of the first message.
