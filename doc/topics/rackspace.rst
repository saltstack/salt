==============================
Getting Started With Rackspace
==============================

Rackspace is a major public cloud platform and is one of the core platforms
that Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set the location of the salt-master
    #
    minion:
        master: saltmaster.example.com

    # Configure Rackspace using the OpenStack plugin
    #
    OPENSTACK.identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
    OPENSTACK.compute_name: cloudServersOpenStack
    OPENSTACK.protocol: ipv4

    # Set the compute region:
    #
    OPENSTACK.compute_region: DFW

    # Configure Rackspace authentication credentials
    #
    OPENSTACK.user: myname
    OPENSTACK.tenant: 123456
    OPENSTACK.apikey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


Compute Region
==============
Rackspace currently has three compute regions which may be used:

.. code-block::

    DFW -> Dallas/Forth Worth
    ORD -> Chicago
    LON -> London

Note: if you are using LON with a UK account, you must use the following identity_url:

.. code-block:: yaml

    OPENSTACK.identity_url: 'https://lon.identity.api.rackspacecloud.com/v2.0/tokens'

Authentication
==============
The ``user`` is the same user as is used to log into the Rackspace Control
Panel. The ``tenant`` and ``apikey`` can be found in the API Keys area of the
Control Panel. The ``apikey`` will be labeled as API Key (and may need to be
generated), and ``tenant`` will be labeled as Cloud Account Number.

An initial profile will be configured in ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    openstack_512:
        provider: openstack
        size: 512MB Standard Instance
        image: Ubuntu 12.04 LTS (Precise Pangolin)

To instantiate a machine based on this profile:

.. code-block:: bash

    # salt-cloud -p openstack_512 myinstance

This will create a virtual machine at Rackspace with the name ``myinstance``.
This operation may take several minutes to complete, depending on the current
load at the Rackspace data center.

Once the instance has been created with salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    # salt myinstance test.ping

