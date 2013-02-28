==============================
Getting Started With RackSpace
==============================

RackSpace is the other major public cloud platform and is one of the core
platforms that Salt Cloud has been build to support.

Set up the cloud config at ``/etc/salt/cloud``:

.. code-block:: yaml

    # Set up an optional default cloud provider
    provider: openstack

    # Set the location of your salt master
    minion:
      master: saltmaster.example.com

    # Set your RackSpace login data using the OpenStack plugin
    OPENSTACK.identity_url: 'https://identity.api.rackspacecloud.com/v2.0/tokens'
    OPENSTACK.compute_name: cloudServersOpenStack
    OPENSTACK.protocol: ipv4

    # You may need to change the compute_region
    OPENSTACK.compute_region: DFW

    # You will certainly need to change each of these
    OPENSTACK.user: myname
    OPENSTACK.tenant: 123456
    OPENSTACK.apikey: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Under Hosting -> Cloud Servers, I see that my servers are provisioned in
either DFW1 or DFW2, however my ``compute_node`` is set to DFW (no trailing
digits).
RackSpace has other regions, but I don't at the time of writing this know
what the other regions are.
If you do, please submit a pull-request to fix this.

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

You can now instantiate a machine based on this profile with a salt
command:

.. code-block:: bash

    # salt-cloud -p openstack_512 foo

This will create a virtual machine at RackSpace with the name ``foo``.
It took about 5 minutes to complete when I tried it.
It may take a little less or a lot more time,
depending on how RackSpace is feeling today.

Once the vm is created it will start up the Salt Minion and connect back to
the Salt Master.
You can confirm this by running the following on the salt master.

.. code-block:: bash

    # salt 'foo' test.ping

You should see your new node responding with a True.

Optional Settings
=================

I don't know about any optional settings for OpenStack / RackSpace
at this time.
