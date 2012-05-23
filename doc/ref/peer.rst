==================
Peer Communication
==================

Salt 0.9.0 introduced the capability for Salt minions to publish commands. The
intent of this feature is not for Salt minions to act as independent brokers
one with another, but to allow Salt minions to pass commands to each other.

The peer interface allows a minion to call out publications on the Salt master
and receive the return data.

Since this presents a viable security risk by allowing minions access to the
master publisher the capability is turned off by default. The minions can be
allowed access to the master publisher on a per minion basis based on regular
expressions. Minions with specific ids can be allowed access to certain Salt
modules and functions.

Configuration
=============

The configuration is done under the peer setting in the Salt master
configuration file, here are a number of configuration possibilities.

The simplest approach is to enable all communication for all minions, this is
only recommended for very secure environments.

.. code-block:: yaml

    peer:
      .*:
        - .*

This configuration will allow minions with IDs ending in example.com access
to the test, ps, and pkg module functions.

.. code-block:: yaml

    peer:
      .*example.com:
        - test.*
        - ps.*
        - pkg.*


The configuration logic is simple, a regular expression is passed for matching
minion ids, and then a list of expressions matching minion functions is
associated with the named minion. For instance, this configuration will also
allow minions ending with foo.org access to the publisher.

.. code-block:: yaml

    peer:
      .*example.com:
        - test.*
        - ps.*
        - pkg.*
      .*foo.org:
        - test.*
        - ps.*
        - pkg.*

