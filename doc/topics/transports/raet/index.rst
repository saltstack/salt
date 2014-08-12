==================
The RAET Transport
==================

.. note::

    The RAET transport is in very early development, it is functional but no
    promises are yet made as to its reliability or security.

    This document is also not yet complete

.. versionadded:: 2014.7.0

The Reliable Asynchronous Event Transport, or RAET, is an alternative transport
medium developed specifically with Salt in mind. It has been developed to
allow queuing to happen up on the application layer and comes with socket
layer encryption. It also abstracts a great deal of control over the socket
layer and makes it easy to bubble up errors and exceptions.

RAET also offers very powerful message routing capabilities, allowing for
messages to be routed between processes on a single machine all the way up to
processes on multiple machines. Messages can also be restricted, allowing
processes to be sent messages of specific types from specific sources
allowing for trust to be established.

Why?
====

Customer and User Request
-------------------------

Why make an alternative transport for Salt? There are many reasons, but the
primary motivation came from customer requests, many large companies came with
requests to run Salt over an alternative transport, the reasoning was varied,
from performance and scaling improvements to licensing concerns. These
customers have partnered with SaltStack to make RAET a reality.

RAET Reliability
================

RAET is reliable, hence the name (Reliable Asynchronous Event Transport).

The concern posed by some over RAET reliability is based on the fact that
RAET used UDP instead of TCP and UDP does not have built in reliability.

RAET itself implements the needed reliability layers that are not natively
present in UDP, this allows RAET to dynamically optimize packet delivery
in a way that keeps it both reliable and asynchronous.

RAET and ZeroMQ
===============

When using RAET, ZeroMQ is not required. RAET is a complete networking
replacement. It is noteworthy that RAET is not a ZeroMQ replacement in a
general sense, the ZeroMQ constructs are not reproduced in RAET, but they are
instead implemented in such a way that is specific to Salt's needs.

RAET is primarily an async communication layer over truly async connections,
defaulting to UDP. ZeroMQ is over TCP and abstracts async constructs within the
socket layer.

Salt is not dropping ZeroMQ support and has no immediate plans to do so.

Encryption
==========

RAET uses Dan Bernstein's NACL encryption libraries and CurveCP handshake.
The libnacl python binding binds to both libsodium and tweetnacl to execute
the underlying cryptography.

Using RAET in Salt
==================

Using RAET in Salt is easy, the main difference is that the core dependencies
change, instead of needing pycrypto, M2Crypto, ZeroMQ and PYZMQ, the packages
libsodium, libnacl and ioflo are required. Encryption is handled very cleanly
by libnacl, while the queueing and flow control is handled by
ioflo. Distribution packages are forthcoming, but libsodium can be easily
installed from source, or many distributions do ship packages for it.
The libnacl and ioflo packages can be easily installed from pypi, distribution
packages are in the works.

Once the new deps are installed the 2014.7 release or higher of Salt needs to
be installed.

Once installed, modify the configuration files for the minion and master to
set the transport to raet:

``/etc/salt/master``:

.. code-block:: yaml

    transport: raet


``/etc/salt/minion``:

.. code-block:: yaml

    transport: raet


Now start salt as it would normally be started, the minion will connect to the
master and share long term keys, which can then in turn be managed via
salt-key. Remote execution and salt states will function in the same way as
with Salt over ZeroMQ.
