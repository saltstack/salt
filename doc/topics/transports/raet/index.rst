.. _raet:

==================
The RAET Transport
==================

.. note::

    The RAET transport is in very early development, it is functional but no
    promises are yet made as to its reliability or security.
    As for reliability and security, the encryption used has been audited and
    our tests show that raet is reliable. With this said we are still conducting
    more security audits and pushing the reliability.
    This document outlines the encryption used in RAET

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

Using RAET in Salt
==================

Using RAET in Salt is easy, the main difference is that the core dependencies
change, instead of needing pycrypto, M2Crypto, ZeroMQ, and PYZMQ, the packages
`libsodium`_, libnacl, ioflo, and raet are required. Encryption is handled very cleanly
by libnacl, while the queueing and flow control is handled by
ioflo. Distribution packages are forthcoming, but `libsodium`_ can be easily
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

Limitations
===========

The 2014.7 release of RAET is not complete! The Syndic and Multi Master have
not been completed yet and these are slated for completion in the 2015.5.0
release.

Also, Salt-Raet allows for more control over the client but these hooks have
not been implemented yet, thereforre the client still uses the same system
as the ZeroMQ client. This means that the extra reliability that RAET exposes
has not yet been implemented in the CLI client.

Why?
====

Customer and User Request
-------------------------

Why make an alternative transport for Salt? There are many reasons, but the
primary motivation came from customer requests, many large companies came with
requests to run Salt over an alternative transport, the reasoning was varied,
from performance and scaling improvements to licensing concerns. These
customers have partnered with SaltStack to make RAET a reality.

More Capabilities
-----------------

RAET has been designed to allow salt to have greater communication
capabilities. It has been designed to allow for development into features
which out ZeroMQ topologies can't match.

Many of the proposed features are still under development and will be
announced as they enter proof of concept phases, but these features include
`salt-fuse` - a filesystem over salt, `salt-vt` - a parallel api driven shell
over the salt transport and many others.

RAET Reliability
================

RAET is reliable, hence the name (Reliable Asynchronous Event Transport).

The concern posed by some over RAET reliability is based on the fact that
RAET uses UDP instead of TCP and UDP does not have built in reliability.

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

RAET uses Dan Bernstein's NACL encryption libraries and `CurveCP`_ handshake.
The libnacl python binding binds to both `libsodium`_ and tweetnacl to execute
the underlying cryptography. This allows us to completely rely on an
externally developed cryptography system.

Programming Intro
=================

.. toctree::

   programming_intro

.. _libsodium: http://doc.libsodium.org/
.. _CurveCP: http://curvecp.org/
