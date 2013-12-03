==============================
Getting Started With OpenStack
==============================

OpenStack is one the most popular cloud projects. It's an open source project
to build public and/or private clouds. You can use Salt Cloud to launch
OpenStack instances.

* Using the new format, set up the cloud configuration at 
  ``/etc/salt/cloud.providers`` or 
  ``/etc/salt/cloud.providers.d/openstack.conf``:

.. code-block:: yaml

    my-openstack-config:
      # Set the location of the salt-master
      #
      minion:
        master: saltmaster.example.com

      # Configure the OpenStack driver
      #
      identity_url: http://identity.youopenstack.com/v2.0/
      compute_name: nova
      protocol: ipv4

      compute_region: RegionOne

      # Configure Openstack authentication credentials
      #
      user: myname
      password: 123456
      # tenant is the project name
      tenant: myproject

      provider: openstack



Using nova client to get information from OpenStack
===================================================

One of the best ways to get information about OpenStack is using the novaclient
python package (available in pypi as python-novaclient). The client
configuration is a set of environment variables that you can get from the
Dashboard. Log in and then go to Project -> Access & security -> API Access and
download the "OpenStack RC file". Then:

.. code-block:: yaml

    source /path/to/your/rcfile
    nova credentials
    nova endpoints

In the ``nova endpoints`` output you can see the information about
``compute_region`` and ``compute_name``.


Compute Region
==============

It depends on the OpenStack cluster that you are using. Please, have a look at
the previous sections.


Authentication
==============

The ``user`` and ``password`` is the same user as is used to log into the
OpenStack Dashboard.


Profiles
========

Here is an example of a profile:

.. code-block:: yaml

    openstack_512:
        provider: my-openstack-config
        size: m1.tiny
        image: cirros-0.3.1-x86_64-uec
        ssh_key_file: /tmp/test.pem

``size`` can be one of the options listed in the output of ``nova flavor-list``.

``image`` can be one of the options listed in the output of ``nova image-list``.

