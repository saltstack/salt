.. _cache:

=================
Minion Data Cache
=================

.. versionadded:: 2016.11.0

The Minion data cache contains the Salt Mine data, minion grains and minion
pillar information cached on the Salt Master. By default, Salt uses the ``localfs`` cache
module to save the data in a ``msgpack`` file on the Salt Master.

.. _pluggable-data-cache:

Pluggable Data Cache
====================

While the default Minion data cache is the ``localfs`` cache, other external
data stores can also be used to store this data such as the ``consul`` module.
To configure a Salt Master to use a different data store, the :conf_master:`cache`
setting needs to be established:

.. code-block:: yaml

    cache: consul

The pluggable data cache streamlines using various Salt topologies such as a
:ref:`Multi-Master <tutorial-multi-master>` or :ref:`Salt Syndics <syndic>` configuration
by allowing the data stored on the Salt Master about a Salt Minion to be available to
other Salt Syndics or Salt Masters that a Salt Minion is connected to.

Additional minion data cache modules can be easily created by modeling the custom data
store after one of the existing cache modules.

See :ref:`cache modules <all-salt.cache>` for a current list.


.. _configure-minion-data-cache:

Configuring the Minion Data Cache
=================================

The default ``localfs`` Minion data cache module doesn't require any
configuration.  External data cache modules with external data stores such as
Consul require a configuration setting in the master config.

Here's an example config for Consul:

.. code-block:: yaml

    consul.host: 127.0.0.1
    consul.port: 8500
    consul.token: None
    consul.scheme: http
    consul.consistency: default
    consul.dc: dc1
    consul.verify: True

    cache: consul
