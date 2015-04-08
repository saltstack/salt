.. _salt-cloud-legacy-configuration:

===============================
Salt Cloud Legacy Configuration
===============================

Starting in Salt-Cloud version 0.8.7, a new cloud provider configuration syntax was
introduced. The new provider configuration allows for multiple configurations of the
same cloud provider where only minor details may change such as the region for an
EC2 instance. The old, legacy format, as documented here, is still supported and
automatically migrated every time a salt-cloud configuration is parsed. However,
the user is warned or salt-cloud will even exit with an error if the legacy cloud
configuration format is mixed with the new, standard cloud configuration format.


Migrating Configurations
========================

If you wish to migrate, there are several alternatives. Since the old syntax
was mainly done on the main cloud configuration file, ``/etc/salt/cloud``, the next
before and after migration examples are helpful to understand the migration.

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
``<provider-alias>: <provider-name>`` should be used.


Legacy Cloud Configurations
===========================

Rackspace
---------

Rackspace cloud requires two configuration options; a ``user`` and an ``apikey``:

.. code-block:: yaml

    RACKSPACE.user: example_user
    RACKSPACE.apikey: 123984bjjas87034


Amazon AWS
----------

A number of configuration options are required for Amazon AWS including ``id``,
``key``, ``keyname``, ``sercuritygroup``, and ``private_key``:

.. code-block:: yaml

    AWS.id: HJGRYCILJLKJYG
    AWS.key: 'kdjgfsgm;woormgl/aserigjksjdhasdfgn'
    AWS.keyname: test
    AWS.securitygroup: quick-start
    AWS.private_key: /root/test.pem


Linode
------

Linode requires a single API key, but the default root password also needs to
be set:

.. code-block:: yaml

    LINODE.apikey: asldkgfakl;sdfjsjaslfjaklsdjf;askldjfaaklsjdfhasldsadfghdkf
    LINODE.password: F00barbaz


Joyent Cloud
------------

The Joyent cloud requires three configuration parameters: The username and
password that are used to log into the Joyent system, as well as the location
of the private SSH key associated with the Joyent account. The SSH key is needed
to send the provisioning commands up to the freshly created virtual machine.

.. code-block:: yaml

    JOYENT.user: fred
    JOYENT.password: saltybacon
    JOYENT.private_key: /root/joyent.pem


GoGrid
------

To use Salt Cloud with GoGrid, log into the GoGrid web interface and create an
API key. Do this by clicking on "My Account" and then going to the API Keys
tab.

The ``GOGRID.apikey`` and the ``GOGRID.sharedsecret`` configuration parameters
need to be set in the cloud provider configuration file to enable interfacing
with GoGrid:

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

If your OpenStack instances only have private IP addresses and a CIDR range of
private addresses are not reachable from the salt-master, you may set your
preference to have Salt ignore it:

.. code-block:: yaml

    OPENSTACK.ignore_cidr: 192.168.0.0/16


DigitalOcean
------------

Using Salt for DigitalOcean requires a ``client_key`` and an ``api_key``. These
can be found in the DigitalOcean web interface, in the "My Settings" section,
under the API Access tab.

.. code-block:: yaml

    DIGITAL_OCEAN.client_key: wFGEwgregeqw3435gDger
    DIGITAL_OCEAN.api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg


Parallels
---------

Using Salt with Parallels requires a ``user``, ``password`` and ``URL``. These
can be obtained from your cloud provider.

.. code-block:: yaml

    PARALLELS.user: myuser
    PARALLELS.password: xyzzy
    PARALLELS.url: https://api.cloud.xmission.com:4465/paci/v1.0/

