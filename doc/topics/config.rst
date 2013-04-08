==================
Core Configuration
==================

A number of core configuration options and some options that are global to the 
VM profiles can be set in the cloud configuration file. By default this file is 
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


Notice that it's not longer required to name a cloud provider's configuration 
after it's provider, it can be an alias, though, an additional configuration 
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
``/etc/salt/cloud.providers/aws-migrated.conf``:


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


While migrating the cloud providers configuration, if the provider alias(from 
the above example ``my-aws-migrated-config``) changes from what you had(from 
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

This new syntax also changes the interaction with ``salt-cloud`` binary.  
``--list-location``, ``--list-images`` and ``--list-sizes`` which needs a cloud 
provider as an argument. Since 0.8.7 the argument used should be the configured 
cloud provider alias. If the provider alias only as a single entry, use 
``<provider-alias>``.  If it has multiple entries, 
``<provider-alias>:<provider-name>`` should be used.



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

The Joyent cloud requires three configuration parameters. The user name and 
password that are used to log into the Joyent system, and the location of the 
private ssh key associated with the Joyent account. The ssh key is needed to 
send the provisioning commands up to the freshly created virtual machine,

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


IBM SmartCloud Enterprise
-------------------------

In addition to a username and password, the IBM SCE module requires an SSH key, 
which is currently configured inside IBM's web interface. A location is also 
required to create instances, but not to query their cloud. This is important, 
because you need to use salt-cloud --list-locations (with the other options 
already set) in order to find the name of the location that you want to use.

* Using the old format:

.. code-block:: yaml

  IBMSCE.user: myuser@mycorp.com
  IBMSCE.password: mypass
  IBMSCE.ssh_key_name: mykey
  IBMSCE.ssh_key_file: '/etc/salt/ibm/mykey.pem'
  IBMSCE.location: Raleigh



* Using the new configuration format:

.. code-block:: yaml

    my-ibmsce-config:
      user: myuser@mycorp.com
      password: mypass
      ssh_key_name: mykey
      ssh_key_file: '/etc/salt/ibm/mykey.pem'
      location: Raleigh
      provider: ibmsce


**NOTE**: With the new providers configuration syntax you would have 
``provider: my-imbsce-config`` instead of ``provider: ibmsce`` on a profile 
configuration.


Extending Profiles and Cloud Providers Configuration
====================================================

As of 0.8.7, the option to extend both the profiles and cloud providers 
configuration and avoid duplication was added. The extends feature works on the 
current profiles configuration, but, regarding the cloud providers 
configuration, **only** works in the new syntax and respective configuration 
files, ie, ``/etc/salt/salt/cloud.providers`` or 
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

