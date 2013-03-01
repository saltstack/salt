==============================
Getting Started With Rackspace
==============================

Rackspace is a major public cloud platform and is one of the core
platforms that Salt Cloud has been built to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up an optional default cloud provider
    provider: openstack

    # Set the location of your salt master
    minion:
      master: saltmaster.example.com

    # Set your Rackspace login data using the OpenStack plugin
    OPENSTACK.identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
    OPENSTACK.compute_name: cloudServersOpenStack
    OPENSTACK.protocol: ipv4

    # You may need to change the compute_region
    OPENSTACK.compute_region: DFW

    # You will certainly need to change each of these
    OPENSTACK.user: myname
    OPENSTACK.tenant: 123456
    OPENSTACK.apikey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

For ``compute_node``, use one of ``DFW``, ``ORD``, or ``LON``.
These are Dallas, Chicago and London respectively.
If you are not sure which of these to use, open the Rackspace web Cloud Control Panel.
Look under Hosting -> Cloud Servers, and you will see a Datacenter column on the far right.
Note that trailing digits should be ommitted.
For example, servers in either DFW1 or DFW2 should have a ``compute_node`` of DFW.

For the ``user``, ``tenant`` and ``apikey``, log into rackspace and go to
Your Account -> API Access.
If you don't already have an API Access Key, go ahead and generate one.
Otherwise, that's your ``apikey``.
If you prefer, the openstack code supports using a ``password`` instead
of an apikey for authentication.
The Cloud Account Number directly below that is what you want for ``tenant``.

Set up an initial profile at ``/etc/salt/cloud.profiles``:

.. code-block:: yaml

    openstack_512:
        provider: openstack
        size: 512MB Standard Instance
        image: Ubuntu 12.04 LTS (Precise Pangolin)

Now instantiate a machine based on this profile with a salt command:

.. code-block:: bash

    # salt-cloud -p openstack_512 foo

This will create a virtual machine at Rackspace with the name ``foo``.
At the time of writing (2013-Feb) this operation takes anywhere from 2 to 25 minutes to complete.
Since it is entirely dependant on Rackspace's load, your mileage may (and will) vary.

Once the vm is created it will start up the Salt Minion and connect back to
the Salt Master.
You can confirm this by running the following on the salt master.

.. code-block:: bash

    # salt 'foo' cmd.run 'uname -a'

You should see your new node responding.

Optional Settings
=================

Currently there are no optional settings for OpenStack / Rackspace.
