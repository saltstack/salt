==================
Core Configuration
==================

A number of core configuration options and some options that are global to
the vm profiles can be set in the cloud config file. By default this file is
located at ``/etc/salt/cloud``.

Minion Configuration
====================

The default minion configuration is set up in this file. This is where the
minions that are created derive their configuration.

.. code-block:: yaml

    minion:
      master: saltmaster.example.com

This is the location in particular to specify the location of the salt master.

Cloud Configurations
====================

The data specific to interacting with public clouds is set up here.

Rackspace
---------

Rackspace cloud requires two configuration options:

.. code-block:: yaml

    RACKSPACE.user: example_user
    RACKSPACE.key: 123984bjjas87034

Amazon AWS
----------

A number of configuration options are required for Amazon EC2:

.. code-block:: yaml

    EC2.id: HJGRYCILJLKJYG
    EC2.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    EC2.keyname: test
    EC2.securitygroup: quick-start
    EC2.private_key: /root/test.pem

Linode
------

Linode requires a single api key, but the default root password also needs
to be set:

.. code-block:: yaml

    LINODE.apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
    LINODE.password: F00barbaz

The password needs to be 8 characters and contain lowercase, uppercase and
numbers.
