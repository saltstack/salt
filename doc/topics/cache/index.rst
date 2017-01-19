.. _cache:

=================
Minion Data Cache
=================

The Minion Data Cache contains the Salt Mine data and other minion info cached
on the Salt master.  By default Salt uses the `localfs` cache module to save
the data in a msgpack file on the Salt master.  Other external data stores can
also be used to store this data such as the `Consul` module.

See :ref:`cache modules <all-salt.cache>` for a current list.


Configuring the Minion Data Cache
=================================

The default `localfs` Minion data cache module doesn't require any
configuration.  External data cache modules with external data stores such as
Consul require a configuration setting in the master config.

Here's an exampls config for Consul:

.. code-block:: yaml

    consul.host: 127.0.0.1
    consul.port: 8500
    consul.token: None
    consul.scheme: http
    consul.consistency: default
    consul.dc: dc1
    consul.verify: True

