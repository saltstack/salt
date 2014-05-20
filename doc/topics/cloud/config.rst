==================
Core Configuration
==================

A number of core configuration options and some options that are global to the
VM profiles can be set in the cloud configuration file. By default this file is
located at ``/etc/salt/cloud``.

Thread Pool Size
====================

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


New Cloud Configuration Syntax
==============================

The data specific to interacting with public clouds is set up here.

**ATTENTION**: Since version 0.8.7 a new cloud provider configuration syntax
was implemented.  It will allow for multiple configurations of the same cloud
provider where only minor details can change, for example, the region for an
EC2 instance. While the old format is still supported and automatically
migrated every time salt-cloud configuration is parsed, a choice was made to
warn the user or even exit with an error if both formats are mixed.


Migrating Configurations
------------------------

If you wish to migrate, there are several alternatives. Since the old syntax
was mainly done on the main cloud configuration file, see the next before and
after migration example.

* Before migration in ``/etc/salt/cloud``:

.. code-block:: yaml

    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWS.keyname: test
    AWS.securitygroup: quick-start
    AWS.private_key: /root/test.pem


* After migration in ``/etc/salt/cloud``:

.. code-block:: yaml

    providers:
      my-aws-migrated-config:
        id: HJGRYCILJLKJYG
        key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
        keyname: test
        securitygroup: quick-start
        private_key: /root/test.pem
        provider: aws


Notice that it's no longer required to name a cloud provider's configuration
after its provider; it can be an alias, though an additional configuration
key is added, ``provider``. This allows for multiple configuration for the same
cloud provider to coexist.

While moving towards an improved and extensible configuration handling
regarding the cloud providers, ``--providers-config``, which defaults to
``/etc/salt/cloud.providers``, was added to the cli parser.  It allows for the
cloud providers configuration to be provided in a different file, and/or even
any matching file on a sub-directory, ``cloud.providers.d/*.conf`` which is
relative to the providers configuration file(with the above configuration file
as an example, ``/etc/salt/cloud.providers.d/*.conf``).

So, using the example configuration above, after migration in
``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/aws-migrated.conf``:


.. code-block:: yaml

    my-aws-migrated-config:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: quick-start
      private_key: /root/test.pem
      provider: aws



Notice that on this last migrated example, it **no longer** includes the
``providers`` starting key.


While migrating the cloud providers configuration, if the provider alias (from
the above example ``my-aws-migrated-config``) changes from what you had (from
the above example ``aws``), you will also need to change the ``provider``
configuration key in the defined profiles.

* From:

.. code-block:: yaml

    rhel_aws:
      provider: aws
      image: ami-e565ba8c
      size: Micro Instance


* To:

.. code-block:: yaml

    rhel_aws:
      provider: my-aws-migrated-config
      image: ami-e565ba8c
      size: Micro Instance


This new configuration syntax even allows you to have multiple cloud
configurations under the same alias, for example:


.. code-block:: yaml

    production-config:
      - id: HJGRYCILJLKJYG
        key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
        keyname: test
        securitygroup: quick-start
        private_key: /root/test.pem

      - user: example_user
        apikey: 123984bjjas87034
        provider: rackspace



**Notice the dash and indentation on the above example.**


Having multiple entries for a configuration alias also makes the ``provider``
key on any defined profile to change, see the example:


.. code-block:: yaml

    rhel_aws_dev:
      provider: production-config:aws
      image: ami-e565ba8c
      size: Micro Instance

    rhel_aws_prod:
      provider: production-config:aws
      image: ami-e565ba8c
      size: High-CPU Extra Large Instance


    database_prod:
      provider: production-config:rackspace
      image: Ubuntu 12.04 LTS
      size: 256 server



Notice that because of the multiple entries, one has to be explicit about the
provider alias and name, from the above example, ``production-config:aws``.

This new syntax also changes the interaction with the ``salt-cloud`` binary.
``--list-location``, ``--list-images`` and ``--list-sizes`` which needs a cloud
provider as an argument. Since 0.8.7 the argument used should be the configured
cloud provider alias. If the provider alias only has a single entry, use
``<provider-alias>``.  If it has multiple entries,
``<provider-alias>:<provider-name>`` should be used.



Pillar Configuration
====================

It is possible to configure cloud providers using pillars.  This is only used
when inside the cloud module.  You can setup a variable called ``clouds`` that
contains your profile and provider to pass that information to the cloud
servers instead of having to copy the full configuration to every minion.

In your pillar file, you would use something like this.

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
          flush_mine_on_destroy: True

        ubuntu-openstack:
          provider: my-openstack
          size: performance1-8
          image: bb02b1a3-bc77-4d17-ab5b-421d89850fca
          script_args: git develop
          flush_mine_on_destroy: True

**NOTE**: This is only valid in the cloud module, so also in the cloud state.
This does not work with the salt-cloud binary.



Cloud Configurations
====================

Rackspace
---------

Rackspace cloud requires two configuration options:

* Using the old format:

.. code-block:: yaml

    RACKSPACE.user: example_user
    RACKSPACE.apikey: 123984bjjas87034



* Using the new configuration format:

.. code-block:: yaml

    my-rackspace-config:
      user: example_user
      apikey: 123984bjjas87034
      provider: rackspace


**NOTE**: With the new providers configuration syntax you would have ``provider:
rackspace-config`` instead of ``provider: rackspace`` on a profile
configuration.


Amazon AWS
----------

A number of configuration options are required for Amazon AWS:

* Using the old format:

.. code-block:: yaml

    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWS.keyname: test
    AWS.securitygroup: quick-start
    AWS.private_key: /root/test.pem


* Using the new configuration format:

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


**NOTE**: With the new providers configuration syntax you would have
``provider: my-aws-quick-start`` or ``provider: my-aws-default`` instead of
``provider: aws`` on a profile configuration.


Linode
------

Linode requires a single API key, but the default root password also needs to
be set:

* Using the old format:

.. code-block:: yaml

    LINODE.apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
    LINODE.password: F00barbaz


* Using the new configuration format:

.. code-block:: yaml

    my-linode-config:
      apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
      password: F00barbaz
      provider: linode


**NOTE**: With the new providers configuration syntax you would have
``provider: my-linode-config`` instead of ``provider: linode`` on a profile
configuration.

The password needs to be 8 characters and contain lowercase, uppercase and
numbers.


Joyent Cloud
------------

The Joyent cloud requires three configuration parameters. The username and
password that are used to log into the Joyent system, and the location of the
private SSH key associated with the Joyent account. The SSH key is needed to
send the provisioning commands up to the freshly created virtual machine.

* Using the old format:

.. code-block:: yaml

    JOYENT.user: fred
    JOYENT.password: saltybacon
    JOYENT.private_key: /root/joyent.pem


* Using the new configuration format:

.. code-block:: yaml

    my-joyent-config:
        user: fred
        password: saltybacon
        private_key: /root/joyent.pem
        provider: joyent


**NOTE**: With the new providers configuration syntax you would have
``provider: my-joyent-config`` instead of ``provider: joyent`` on a profile
configuration.


GoGrid
------

To use Salt Cloud with GoGrid log into the GoGrid web interface and create an
API key. Do this by clicking on "My Account" and then going to the API Keys
tab.

The GOGRID.apikey and the GOGRID.sharedsecret configuration parameters need to
be set in the configuration file to enable interfacing with GoGrid:

* Using the old format:

.. code-block:: yaml

    GOGRID.apikey: asdff7896asdh789
    GOGRID.sharedsecret: saltybacon


* Using the new configuration format:

.. code-block:: yaml

    my-gogrid-config:
      apikey: asdff7896asdh789
      sharedsecret: saltybacon
      provider: gogrid


**NOTE**: With the new providers configuration syntax you would have
``provider: my-gogrid-config`` instead of ``provider: gogrid`` on a profile
configuration.


OpenStack
---------

OpenStack configuration differs between providers, and at the moment several
options need to be specified. This module has been officially tested against
the HP and the Rackspace implementations, and some examples are provided for
both.

* Using the old format:

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
  OPENSTACK.protocol: ipv4
  OPENSTACK.compute_region: DFW
  OPENSTACK.protocol: ipv4
  OPENSTACK.user: myuser
  OPENSTACK.tenant: 5555555
  OPENSTACK.password: mypass


If you have an API key for your provider, it may be specified instead of a
password:

.. code-block:: yaml

  OPENSTACK.apikey: 901d3f579h23c8v73q9


* Using the new configuration format:

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


**NOTE**: With the new providers configuration syntax you would have
``provider: my-openstack-hp-config`` or ``provider:
my-openstack-rackspace-config`` instead of ``provider: openstack`` on a profile
configuration.


You will certainly need to configure the ``user``, ``tenant`` and either
``password`` or ``apikey``.


If your OpenStack instances only have private IP addresses and a CIDR range of
private addresses are not reachable from the salt-master, you may set your
preference to have Salt ignore it. Using the old could configurations syntax:

.. code-block:: yaml

    OPENSTACK.ignore_cidr: 192.168.0.0/16


Using the new syntax:

.. code-block:: yaml

    my-openstack-config:
      ignore_cidr: 192.168.0.0/16


For in-house OpenStack Essex installation, libcloud needs the service_type :

.. code-block:: yaml

  my-openstack-config:
    identity_url: 'http://control.openstack.example.org:5000/v2.0/'
    compute_name : Compute Service
    service_type : compute



Digital Ocean
-------------

Using Salt for Digital Ocean requires a client_key and an api_key. These can be
found in the Digital Ocean web interface, in the "My Settings" section, under
the API Access tab.

* Using the old format:

.. code-block:: yaml

    DIGITAL_OCEAN.client_key: wFGEwgregeqw3435gDger
    DIGITAL_OCEAN.api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg


* Using the new configuration format:

.. code-block:: yaml

    my-digitalocean-config:
      provider: digital_ocean
      client_key: wFGEwgregeqw3435gDger
      api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg
      location: New York 1


**NOTE**: With the new providers configuration syntax you would have
``provider: my-digitalocean-config`` instead of ``provider: digital_ocean`` on a
profile configuration.


Parallels
---------

Using Salt with Parallels requires a user, password and URL. These can be
obtained from your cloud provider.

* Using the old format:

.. code-block:: yaml

    PARALLELS.user: myuser
    PARALLELS.password: xyzzy
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/


* Using the new configuration format:

.. code-block:: yaml

    my-parallels-config:
      user: myuser
      password: xyzzy
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      provider: parallels


**NOTE**: With the new providers configuration syntax you would have
``provider: my-parallels-config`` instead of ``provider: parallels`` on a
profile configuration.

Proxmox
---------

Using Salt with Proxmox requires a user, password and URL. These can be
obtained from your cloud provider. Both PAM and PVE users can be used.

* Using the new configuration format:

.. code-block:: yaml

    my-proxmox-config:
      provider: proxmox
      user: saltcloud@pve
      password: xyzzy
      url: your.proxmox.host
  
lxc
---

The lxc driver is a new, experimental driver for installing Salt on
newly provisionned (via saltcloud) lxc containers. It will in turn use saltify to install
salt an rattach the lxc container as a new lxc minion.
As soon as we can, we manage baremetal operation over SSH.
You can also destroy those containers via this driver.

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

.. _config_saltify:

Saltify
-------

The Saltify driver is a new, experimental driver for installing Salt on
existing machines (virtual or bare metal). Because it does not use an actual
cloud provider, it needs no configuration in the main cloud config file.
However, it does still require a profile to be set up, and is most useful when
used inside a map file. The key parameters to be set are ``ssh_host``,
``ssh_username`` and either ``ssh_keyfile`` or ``ssh_password``. These may all
be set in either the profile or the map. An example configuration might use the
following in cloud.profiles:

.. code-block:: yaml

    make_salty:
      provider: saltify

And in the map file:

.. code-block:: yaml

    make_salty:
      - myinstance:
        ssh_host: 54.262.11.38
        ssh_username: ubuntu
        ssh_keyfile: '/etc/salt/mysshkey.pem'
        sudo: True


Extending Profiles and Cloud Providers Configuration
====================================================

As of 0.8.7, the option to extend both the profiles and cloud providers
configuration and avoid duplication was added. The extends feature works on the
current profiles configuration, but, regarding the cloud providers
configuration, **only** works in the new syntax and respective configuration
files, i.e. ``/etc/salt/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.


Extending Profiles
------------------

Some example usage on how to use ``extends`` with profiles. Consider
``/etc/salt/salt/cloud.profiles`` containing:

.. code-block:: yaml

    development-instances:
      provider: my-ec2-config
      size: Micro Instance
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
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-09b61d60',
      'profile': 'CentOS-5',
      'provider': 'my-aws-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-54cf5c3d',
      'profile': 'Amazon-Linux-AMI-2012.09-64bit',
      'provider': 'my-ec2-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'profile': 'development-instances',
      'provider': 'my-ec2-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
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

