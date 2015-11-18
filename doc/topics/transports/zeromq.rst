================
Zeromq Transport
================

.. note::

    Zeromq is the current default transport within Salt

Zeromq is a messaging library with bindings into many languages. Zeromq implements
a socket interface for message passing, with specific semantics for the socket type.


Pub Channel
===========
The pub channel is implemented using zeromq's pub/sub sockets. By default we don't
use zeromq's filtering, which means that all publish jobs are sent to all minions
and filtered minion side. Zeromq does have publisher side filtering which can be
enabled in salt using :conf_master:`zmq_filtering`.


Req Channel
===========
The req channel is implemented using zeromq's req/rep sockets. These sockets
enforce a send/recv pattern, which forces salt to serialize messages through these
socket pairs. This means that although the interface is asynchronous on the minion
we cannot send a second message until we have received the reply of the first message.
