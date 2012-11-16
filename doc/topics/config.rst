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
    RACKSPACE.apikey: 123984bjjas87034

Amazon AWS
----------

A number of configuration options are required for Amazon AWS:

.. code-block:: yaml

    AWS.id: HJGRYCILJLKJYG
    AWSAWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWSAWS.keyname: test
    AWSAWS.securitygroup: quick-start
    AWSAWS.private_key: /root/test.pem

Linode
------

Linode requires a single api key, but the default root password also needs
to be set:

.. code-block:: yaml

    LINODE.apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
    LINODE.password: F00barbaz

The password needs to be 8 characters and contain lowercase, uppercase and
numbers.

Joyent Cloud
------------

The Joyent cloud requires three configuration paramaters. The user name and
password that are used to log into the Joyent system, and the location of
the private ssh key associated with the Joyent account. The ssh key is needed
to send the provisioning commands up to the freshly created virtual machine,

.. code-block:: yaml

    JOYENT.user: fred
    JOYENT.password: saltybacon
    JOYENT.private_key: /root/joyent.pem

GoGrid
------

To use Salt Cloud with GoGrid log into the GoGrid web interface and
create an api key. Do this by clicking on "My Account" and then going to the
API Keys tab.

The GOGRID.apikey and the GOGRID.sharedsecret configuration paramaters need to
be set in the config file to enable interfacing with GoGrid:

.. code-block:: yaml

    GOGRID.apikey: asdff7896asdh789
    GOGRID.sharedsecret: saltybacon

OpenStack
---------

OpenStack configuration differs between providers, and at the moment several
options need to be specified. This module has been officially tested against
the HP and the Rackspace implementations, and some examples are provided for
both.

.. code-block:: yaml

  # For HP
  OPENSTACK.identity_url: 'https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/'
  OPENSTACK.compute_name: Compute
  OPENSTACK.compute_region: 'az-1.region-a.geo-1'
  OPENSTACK.tenant: myuser-tenant1
  OPENSTACK.user: myuser
  OPENSTACK.ssh_key_name: mykey
  OPENSTACK.ssh_key_file: '/etc/salt/hpcloud/mykey.pem'
  OPENSTACK.password: mypass

  # For Rackspace
  OPENSTACK.identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
  OPENSTACK.compute_name: cloudServersOpenStack
  OPENSTACK.compute_region: DFW
  OPENSTACK.tenant: 5555555
  OPENSTACK.user: myuser
  OPENSTACK.password: mypass
  OPENSTACK.protocol: ipv4

It is important to note that currently, only password-based authentication is
provided through the Salt Cloud OpenStack module.

IBM SmartCloud Enterprise
-------------------------

In addition to a username and password, the IBM SCE module requires an SSH key,
which is currently configured inside IBM's web interface. A location is also
required to create instances, but not to query their cloud. This is important,
because you need to use salt-cloud --list-locations (with the other options
already set) in order to find the name of the location that you want to use.

.. code-block:: yaml

  IBMSCE.user: myuser@mycorp.com
  IBMSCE.password: mypass
  IBMSCE.ssh_key_name: mykey
  IBMSCE.ssh_key_file: '/etc/salt/ibm/mykey.pem'
  IBMSCE.location: Raleigh


