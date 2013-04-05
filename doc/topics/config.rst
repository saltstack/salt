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

While moving towards an improved and extensible configuration handling 
regarding the cloud providers, ``--providers-config``, which defaults to 
``/etc/salt/cloud.providers`` was added to the cli parser.  It allows for the 
cloud providers configuration to be provided in a different file, and/or even 
any matching file on a sub-directory, ``cloud.providers.d/*.conf`` which is 
relative to the providers configuration file(with the above configuration file 
as an example, ``/etc/salt/cloud.providers.d/*.conf``).


Rackspace
---------

Rackspace cloud requires two configuration options:

* Using the old format:

.. code-block:: yaml

    RACKSPACE.user: example_user
    RACKSPACE.apikey: 123984bjjas87034



* Using the new configuration format:

.. code-block:: yaml

    rackspace-config:
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

    aws-quick-start:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: quick-start
      private_key: /root/test.pem
      provider: aws

    aws-default:
      id: HJGRYCILJLKJYG
      key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
      keyname: test
      securitygroup: default
      private_key: /root/test.pem
      provider: aws


**NOTE**: With the new providers configuration syntax you would have 
``provider: aws-quick-start`` or ``provider: aws-default`` instead of 
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

    linode-foo:
      apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
      password: F00barbaz
      provider: linode


**NOTE**: With the new providers configuration syntax you would have ``provider: 
linode-foo`` instead of ``provider: linode`` on a profile configuration.

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

    joyent-config:
        user: fred
        password: saltybacon
        private_key: /root/joyent.pem
        provider: joyent


**NOTE**: With the new providers configuration syntax you would have ``provider: 
joyent-config`` instead of ``provider: joyent`` on a profile configuration.


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

    gogrid-config:
      apikey: asdff7896asdh789
      sharedsecret: saltybacon
      provider: gogrid


**NOTE**: With the new providers configuration syntax you would have 
``provider: gogrid-config`` instead of ``provider: gogrid`` on a profile 
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
    openstack-hp-config:
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
    openstack-rackspace-config:
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

    openstack-hp-config:
      apikey: 901d3f579h23c8v73q9

    openstack-rackspace-config:
      apikey: 901d3f579h23c8v73q9


**NOTE**: With the new providers configuration syntax you would have 
``provider: openstack-hp-config`` or ``provider: openstack-rackspace-config`` 
instead of ``provider: openstack`` on a profile configuration.


You will certainly need to configure the ``user``, ``tenant`` and either 
``password`` or ``apikey``.


If your OpenStack instances only have private IP addresses and a CIDR range of
private addresses are not reachable from the salt-master, you may set your
preference to have Salt ignore it. Using the old could configurations syntax:

.. code-block:: yaml

    OPENSTACK.ignore_cidr: 192.168.0.0/16


Using the new syntax:

.. code-block:: yaml

    openstack-config:
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

    ibmsce-config:
      user: myuser@mycorp.com
      password: mypass
      ssh_key_name: mykey
      ssh_key_file: '/etc/salt/ibm/mykey.pem'
      location: Raleigh
      provider: ibmsce


**NOTE**: With the new providers configuration syntax you would have 
``provider: imbsce-config`` instead of ``provider: ibmsce`` on a profile 
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
      provider: ec2-config
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
      provider: aws-config
      image: ami-09b61d60
      extends: development-instances


The above configuration, once parsed would generate the following profiles 
data:

.. code-block:: text

    [{'deploy': False,
      'image': 'ami-08d97e61',
      'profile': 'Fedora-17',
      'provider': 'ec2-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-09b61d60',
      'profile': 'CentOS-5',
      'provider': 'aws-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'image': 'ami-54cf5c3d',
      'profile': 'Amazon-Linux-AMI-2012.09-64bit',
      'provider': 'ec2-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'},
     {'deploy': False,
      'profile': 'development-instances',
      'provider': 'ec2-config',
      'securitygroup': ['default'],
      'size': 'Micro Instance',
      'ssh_username': 'ec2_user'}]

Pretty cool right?


Extending Providers
-------------------

Some example usage on how to use ``extends`` within the cloud providers 
configuration.  Consider ``/etc/salt/salt/cloud.providers`` containing:


.. code-block:: yaml

    develop-envs:
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


    productions-envs:
      - extends: develop-envs:ibmsce
        user: my-production-user@mycorp.com
        location: us-east-1
        availability_zone: us-east-1

