==================
The RAET Transport
==================

.. note::

    The RAET transport is in very early development, it is functional but no
    promises are yet made as to its reliability or security.

    This document is also not yet complete

.. versionadded:: Helium

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
from performance and scaling concerns to licensing concerns. These customers
have partnered with SaltStack to make RAET a reality.

Networking Flexibility
----------------------

forthcoming

Performance
-----------

forthcoming

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

The RAET system in Salt defaults to using CurveCP encryption, the
specifications for which can be found here:
http://curvecp.org

RAET does maintain a few minor differences, primarily in the formatting of the
header and the inline distribution of long term keys. A more complete
explanation of differences can be found here:
<forthcoming>

Using RAET in Salt
==================

Using RAET in Salt is easy, the main difference is that the core dependencies
change, instead of needing pycrypto, M2Crypto, ZeroMQ and PYZMQ, the packages
libsodium, pynacl and ioflo are required. Encryption is handled very cleanly
by libsodium and pynacl, while the queueing and flow control is handled by
ioflo. Distribution packages are forthcoming, but libsodium can be easily
installed from source, or many distributions do ship packages for it.
The pynacl and ioflo packages can be easily installed from pypi, distribution
packages are in the works.

Once the new deps are installed the latest Salt git code needs to be installed.
As of this writing RAET is not available in a stable release of Salt, it must
be installed a git clone:

.. code-block:: bash

    git clone https://github.com/saltstack/salt.git
    cd salt
    python2 setup.py install

.. note::

    This will install Salt directly from git HEAD, there is no promise that
    git HEAD is in a functional state.

Once installed, modify the configuration files for the minion and master to
set the transport to raet (the file_buffer_size and id need to be set to
adress known bugs in the unreleased code as of this writing):

``/etc/salt/master``:

.. code-block:: yaml

    transport: raet
    id: master
    file_buffer_size: 54000


``/etc/salt/minion``:

.. code-block:: yaml

    transport: raet


Now start salt as it would normally be started, the minion will connect to the
master and share long term keys, which can then in turn be managed via
salt-key. Remote execution and salt states will function in the same way as
with Salt over ZeroMQ.
