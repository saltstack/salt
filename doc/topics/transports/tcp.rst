=============
TCP Transport
=============

The tcp transport is an implementation of Salt's transport using raw tcp sockets.
Since this isn't using a pre-defined messaging library we will describe the wire
protocol, message semantics, etc. in this document.

The tcp transport is enabled by changing the :conf_minion:`transport` setting
to ``tcp`` on each Salt minion and Salt master.

.. code-block:: yaml

   transport: tcp

.. warning::

    We currently recommend that when using Syndics that all Masters and Minions
    use the same transport. We're investigating a report of an error when using
    mixed transport types at very heavy loads.

Wire Protocol
=============
This implementation over TCP focuses on flexibility over absolute efficiency.
This means we are okay to spend a couple of bytes of wire space for flexibility
in the future. That being said, the wire framing is quite efficient and looks
like:

.. code-block:: text

    msgpack({'head': SOMEHEADER, 'body': SOMEBODY})

Since msgpack is an iterably parsed serialization, we can simply write the serialized
payload to the wire. Within that payload we have two items "head" and "body".
Head contains header information (such as "message id"). The Body contains the
actual message that we are sending. With this flexible wire protocol we can
implement any message semantics that we'd like-- including multiplexed message
passing on a single socket.

TLS Support
===========

.. versionadded:: 2016.11.1

The TCP transport allows for the master/minion communication to be optionally
wrapped in a TLS connection. Enabling this is simple, the master and minion need
to be using the tcp connection, then the `ssl` option is enabled. The `ssl`
option is passed as a dict and corresponds to the options passed to the
Python `ssl.wrap_socket <https://docs.python.org/3/library/ssl.html#ssl.wrap_socket>`_
function.

A simple setup looks like this, on the Salt Master add the `ssl` option to the
master configuration file:

.. code-block:: yaml

    ssl:
      keyfile: <path_to_keyfile>
      certfile: <path_to_certfile>
      ssl_version: PROTOCOL_TLSv1_2
      ciphers: ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384

The minimal `ssl` option in the minion configuration file looks like this:

.. code-block:: yaml

    ssl: True
    # Versions below 2016.11.4:
    ssl: {}

Specific options can be sent to the minion also, as defined in the Python
`ssl.wrap_socket` function.

.. note::

    While setting the ssl_version is not required, we recommend it. Some older
    versions of python do not support the latest TLS protocol and if this is
    the case for your version of python we strongly recommend upgrading your
    version of Python. Ciphers specification might be omitted, but strongly
    recommended as otherwise all available ciphers will be enabled.


Crypto
======
The current implementation uses the same crypto as the ``zeromq`` transport.


Publish Server and Client
=========================
For the publish server and client we send messages without "message ids" which
the remote end interprets as a one-way send.

.. note::

    As of Salt `2016.3.0 <https://github.com/saltstack/salt/commit/1a395ed7a3e72eac87e81dfa072be9cf049453d3>`_, publishes using ``list`` targeting are sent only to relevant minions and not broadcasted.

    As of Salt `3005 <https://github.com/saltstack/salt/commit/9db1af7147f7e6176e5f226cfedf1654ca038ec1>`_, publishes using ``pcre`` and ``glob`` targeting are also sent only to relevant minions and not broadcasted. Other targeting types are always sent to all minions and rely on minion-side filtering.

.. note::

   Salt CLI defaults to ``glob`` targeting type, so in order to target specific minions without broadcast, you need to use `-L` option, such as ``salt -L my.minion test.ping``, for masters before 3005.


Request Server and Client
=========================
For the request server and client we send messages with a "message id". This
"message id" allows us to multiplex messages across the socket.
