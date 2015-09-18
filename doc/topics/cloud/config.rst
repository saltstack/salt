==================
Core Configuration
==================

A number of core configuration options and some options that are global to the
VM profiles can be set in the cloud configuration file. By default this file is
located at ``/etc/salt/cloud``.


Thread Pool Size
================

When salt cloud is operating in parallel mode via the ``-P`` argument, you can
control the thread pool size by specifying the ``pool_size`` parameter with
a positive integer value.

By default, the thread pool size will be set to the number of VMs that salt
cloud is operating on.

.. code-block:: yaml

    pool_size: 10


Minion Configuration
====================

The default minion configuration is set up in this file. Minions created by
salt-cloud derive their configuration from this file.  Almost all parameters
found in :ref:`Configuring the Salt Minion <configuration-salt-minion>` can
be used here.

.. code-block:: yaml

    minion:
      master: saltmaster.example.com


In particular, this is the location to specify the location of the salt master
and its listening port, if the port is not set to the default.


Cloud Configuration Syntax
==========================

The data specific to interacting with public clouds is set up here.

Cloud provider configuration syntax can live in several places. The first is in
``/etc/salt/cloud``:

.. code-block:: yaml

    # /etc/salt/cloud
    providers:
      my-aws-migrated-config:
        id: HJGRYCILJLKJYG
        key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
        keyname: test
        securitygroup: quick-start
        private_key: /root/test.pem
        provider: aws

Cloud provider configuration data can also be housed in ``/etc/salt/cloud.providers``
or any file matching ``/etc/salt/cloud.providers.d/*.conf``. All files in any of these
locations will be parsed for cloud provider data.

Using the example configuration above:

.. code-block:: yaml

    # /etc/salt/cloud.providers
    # or could be /etc/salt/cloud.providers.d/*.conf
    my-aws-config:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: quick-start
      private_key: /root/test.pem
      provider: aws

.. note::

    Salt Cloud provider configurations within ``/etc/cloud.provider.d/ should not
    specify the ``providers`` starting key.

It is also possible to have multiple cloud configuration blocks within the same alias block.
For example:

.. code-block:: yaml

    production-config:
      - id: HJGRYCILJLKJYG
        key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
        keyname: test
        securitygroup: quick-start
        private_key: /root/test.pem
        provider: aws

      - user: example_user
        apikey: 123984bjjas87034
        provider: rackspace


However, using this configuration method requires a change with profile configuration blocks.
The provider alias needs to have the provider key value appended as in the following example:

.. code-block:: yaml

    rhel_aws_dev:
      provider: production-config:aws
      image: ami-e565ba8c
      size: t1.micro

    rhel_aws_prod:
      provider: production-config:aws
      image: ami-e565ba8c
      size: High-CPU Extra Large Instance

    database_prod:
      provider: production-config:rackspace
      image: Ubuntu 12.04 LTS
      size: 256 server

Notice that because of the multiple entries, one has to be explicit about the provider alias and
name, from the above example, ``production-config: aws``.

This data interactions with the ``salt-cloud`` binary regarding its ``--list-location``,
``--list-images``, and ``--list-sizes`` which needs a cloud provider as an argument. The argument
used should be the configured cloud provider alias. If the provider alias has multiple entries,
``<provider-alias>: <provider-name>`` should be used.

To allow for a more extensible configuration, ``--providers-config``, which defaults to
``/etc/salt/cloud.providers``, was added to the cli parser.  It allows for the providers'
configuration to be added on a per-file basis.


Pillar Configuration
====================

It is possible to configure cloud providers using pillars. This is only used when inside the cloud
module. You can setup a variable called ``cloud`` that contains your profile and provider to pass
that information to the cloud servers instead of having to copy the full configuration to every
minion. In your pillar file, you would use something like this:

.. code-block:: yaml

    cloud:
      ssh_key_name: saltstack
      ssh_key_file: /root/.ssh/id_rsa
      update_cachedir: True
      diff_cache_events: True
      change_password: True

      providers:
        my-nova:
          identity_url: https://identity.api.rackspacecloud.com/v2.0/
          compute_region: IAD
          user: myuser
          api_key: apikey
          tenant: 123456
          provider: nova

        my-openstack:
          identity_url: https://identity.api.rackspacecloud.com/v2.0/tokens
          user: user2
          apikey: apikey2
          tenant: 654321
          compute_region: DFW
          provider: openstack
          compute_name: cloudServersOpenStack

      profiles:
        ubuntu-nova:
          provider: my-nova
          size: performance1-8
          image: bb02b1a3-bc77-4d17-ab5b-421d89850fca
          script_args: git develop

        ubuntu-openstack:
          provider: my-openstack
          size: performance1-8
          image: bb02b1a3-bc77-4d17-ab5b-421d89850fca
          script_args: git develop


Cloud Configurations
====================

Rackspace
---------

Rackspace cloud requires two configuration options; a ``user`` and an ``apikey``:

.. code-block:: yaml

    my-rackspace-config:
      user: example_user
      apikey: 123984bjjas87034
      provider: rackspace-config

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-rackspace-config``.


Amazon AWS
----------

A number of configuration options are required for Amazon AWS including ``id``,
``key``, ``keyname``, ``securitygroup``, and ``private_key``:

.. code-block:: yaml

    my-aws-quick-start:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: quick-start
      private_key: /root/test.pem
      provider: aws

    my-aws-default:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: default
      private_key: /root/test.pem
      provider: aws

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be either ``provider: my-aws-quick-start``
    or ``provider: my-aws-default``.


Linode
------

Linode requires a single API key, but the default root password also needs to
be set:

.. code-block:: yaml

    my-linode-config:
      apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
      password: F00barbaz
      ssh_pubkey: ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKHEOLLbeXgaqRQT9NBAopVz366SdYc0KKX33vAnq+2R user@host
      ssh_key_file: ~/.ssh/id_ed25519
      provider: linode

The password needs to be 8 characters and contain lowercase, uppercase, and
numbers.

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-linode-config``


Joyent Cloud
------------

The Joyent cloud requires three configuration parameters: The username and
password that are used to log into the Joyent system, as well as the location
of the private SSH key associated with the Joyent account. The SSH key is needed
to send the provisioning commands up to the freshly created virtual machine.

.. code-block:: yaml

    my-joyent-config:
      user: fred
      password: saltybacon
      private_key: /root/joyent.pem
      provider: joyent

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-joyent-config``


GoGrid
------

To use Salt Cloud with GoGrid, log into the GoGrid web interface and create an
API key. Do this by clicking on "My Account" and then going to the API Keys
tab.

The ``apikey`` and the ``sharedsecret`` configuration parameters need to
be set in the configuration file to enable interfacing with GoGrid:

.. code-block:: yaml

    my-gogrid-config:
      apikey: asdff7896asdh789
      sharedsecret: saltybacon
      provider: gogrid

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-gogrid-config``.


OpenStack
---------

OpenStack configuration differs between providers, and at the moment several
options need to be specified. This module has been officially tested against
the HP and the Rackspace implementations, and some examples are provided for
both.

.. code-block:: yaml

    # For HP
    my-openstack-hp-config:
      identity_url:
      'https://region-a.geo-1.identity.hpcloudsvc.com:35357/v2.0/'
      compute_name: Compute
      compute_region: 'az-1.region-a.geo-1'
      tenant: myuser-tenant1
      user: myuser
      ssh_key_name: mykey
      ssh_key_file: '/etc/salt/hpcloud/mykey.pem'
      password: mypass
      provider: openstack

    # For Rackspace
    my-openstack-rackspace-config:
      identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
      compute_name: cloudServersOpenStack
      protocol: ipv4
      compute_region: DFW
      protocol: ipv4
      user: myuser
      tenant: 5555555
      password: mypass
      provider: openstack


If you have an API key for your provider, it may be specified instead of a
password:

.. code-block:: yaml

    my-openstack-hp-config:
      apikey: 901d3f579h23c8v73q9

    my-openstack-rackspace-config:
      apikey: 901d3f579h23c8v73q9

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be either ``provider: my-openstack-hp-config``
    or ``provider: my-openstack-rackspace-config``.

You will certainly need to configure the ``user``, ``tenant``, and either
``password`` or ``apikey``.

If your OpenStack instances only have private IP addresses and a CIDR range of
private addresses are not reachable from the salt-master, you may set your
preference to have Salt ignore it:

.. code-block:: yaml

    my-openstack-config:
      ignore_cidr: 192.168.0.0/16

For in-house OpenStack Essex installation, libcloud needs the service_type :

.. code-block:: yaml

    my-openstack-config:
      identity_url: 'http://control.openstack.example.org:5000/v2.0/'
      compute_name : Compute Service
      service_type : compute


DigitalOcean
------------

Using Salt for DigitalOcean requires a ``client_key`` and an ``api_key``. These
can be found in the DigitalOcean web interface, in the "My Settings" section,
under the API Access tab.

.. code-block:: yaml

    my-digitalocean-config:
      provider: digital_ocean
      personal_access_token: xxx
      location: New York 1

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-digital-ocean-config``.


Parallels
---------

Using Salt with Parallels requires a ``user``, ``password`` and ``URL``. These
can be obtained from your cloud provider.

.. code-block:: yaml

    my-parallels-config:
      user: myuser
      password: xyzzy
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      provider: parallels

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-parallels-config``.


Proxmox
-------

Using Salt with Proxmox requires a ``user``, ``password``, and ``URL``. These can be
obtained from your cloud provider. Both PAM and PVE users can be used.

.. code-block:: yaml

    my-proxmox-config:
      provider: proxmox
      user: saltcloud@pve
      password: xyzzy
      url: your.proxmox.host

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: my-proxmox-config``.


LXC
---

The lxc driver uses saltify to install salt and attach the lxc container as a new lxc
minion. As soon as we can, we manage baremetal operation over SSH. You can also destroy
those containers via this driver.

.. code-block:: yaml

    devhost10-lxc:
      target: devhost10
      provider: lxc

And in the map file:

.. code-block:: yaml

    devhost10-lxc:
      provider: devhost10-lxc
      from_container: ubuntu
      backing: lvm
      sudo: True
      size: 3g
      ip: 10.0.3.9
      minion:
        master: 10.5.0.1
        master_port: 4506
      lxc_conf:
        - lxc.utsname: superlxc

.. note::

    In the cloud profile that uses this provider configuration, the syntax for the
    ``provider`` required field would be ``provider: devhost10-lxc``.

.. _config_saltify:

Saltify
-------

The Saltify driver is a new, experimental driver designed to install Salt on a remote
machine, virtual or bare metal, using SSH. This driver is useful for provisioning
machines which are already installed, but not Salted. For more information about using
this driver and for configuration examples, please see the
:ref:`Gettting Started with Saltify <getting-started-with-saltify>` documentation.


Extending Profiles and Cloud Providers Configuration
====================================================

As of 0.8.7, the option to extend both the profiles and cloud providers
configuration and avoid duplication was added. The extends feature works on the
current profiles configuration, but, regarding the cloud providers
configuration, **only** works in the new syntax and respective configuration
files, i.e. ``/etc/salt/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.


.. note::

    Extending cloud profiles and providers is not recursive. For example, a
    profile that is extended by a second profile is possible, but the second
    profile cannot be extended by a third profile.

    Also, if a profile (or provider) is extending another profile and each
    contains a list of values, the lists from the extending profile will
    override the list from the original profile. The lists are not merged
    together.


Extending Profiles
------------------

Some example usage on how to use ``extends`` with profiles. Consider
``/etc/salt/salt/cloud.profiles`` containing:

.. code-block:: yaml

    development-instances:
      provider: my-ec2-config
      size: t1.micro
      ssh_username: ec2_user
      securitygroup:
        - default
      deploy: False

    Amazon-Linux-AMI-2012.09-64bit:
      image: ami-54cf5c3d
      extends: development-instances

    Fedora-17:
      image: ami-08d97e61
      extends: development-instances

    CentOS-5:
      provider: my-aws-config
      image: ami-09b61d60
      extends: development-instances


The above configuration, once parsed would generate the following profiles
data:

.. code-block:: python

    [{'deploy': False,
      'image': 'ami-08d97e61',
      'profile': 'Fedora-17',
      'provider': 'my-ec2-config',
      'securitygroup': ['default'],
      'size': 't1.micro',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-09b61d60',
      'profile': 'CentOS-5',
      'provider': 'my-aws-config',
      'securitygroup': ['default'],
      'size': 't1.micro',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-54cf5c3d',
      'profile': 'Amazon-Linux-AMI-2012.09-64bit',
      'provider': 'my-ec2-config',
      'securitygroup': ['default'],
      'size': 't1.micro',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'profile': 'development-instances',
      'provider': 'my-ec2-config',
      'securitygroup': ['default'],
      'size': 't1.micro',
      'ssh_username': 'ec2_user'}]

Pretty cool right?


Extending Providers
-------------------

Some example usage on how to use ``extends`` within the cloud providers
configuration.  Consider ``/etc/salt/salt/cloud.providers`` containing:


.. code-block:: yaml

    my-develop-envs:
      - id: HJGRYCILJLKJYG
        key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
        keyname: test
        securitygroup: quick-start
        private_key: /root/test.pem
        location: ap-southeast-1
        availability_zone: ap-southeast-1b
        provider: aws

      - user: myuser@mycorp.com
        password: mypass
        ssh_key_name: mykey
        ssh_key_file: '/etc/salt/ibm/mykey.pem'
        location: Raleigh
        provider: ibmsce


    my-productions-envs:
      - extends: my-develop-envs:ibmsce
        user: my-production-user@mycorp.com
        location: us-east-1
        availability_zone: us-east-1


The above configuration, once parsed would generate the following providers
data:

.. code-block:: python

    'providers': {
        'my-develop-envs': [
            {'availability_zone': 'ap-southeast-1b',
             'id': 'HJGRYCILJLKJYG',
             'key': 'kdjgfsgm;woormgl/aserigjksjdhasdfgn',
             'keyname': 'test',
             'location': 'ap-southeast-1',
             'private_key': '/root/test.pem',
             'provider': 'aws',
             'securitygroup': 'quick-start'
            },
            {'location': 'Raleigh',
             'password': 'mypass',
             'provider': 'ibmsce',
             'ssh_key_file': '/etc/salt/ibm/mykey.pem',
             'ssh_key_name': 'mykey',
             'user': 'myuser@mycorp.com'
            }
        ],
        'my-productions-envs': [
            {'availability_zone': 'us-east-1',
             'location': 'us-east-1',
             'password': 'mypass',
             'provider': 'ibmsce',
             'ssh_key_file': '/etc/salt/ibm/mykey.pem',
             'ssh_key_name': 'mykey',
             'user': 'my-production-user@mycorp.com'
            }
        ]
    }
