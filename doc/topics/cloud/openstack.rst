==============================
Getting Started With OpenStack
==============================

OpenStack is one the most popular cloud projects. It's an open source project
to build public and/or private clouds. You can use Salt Cloud to launch
OpenStack instances.


Dependencies
============
* Libcloud >= 0.13.2


Configuration
=============
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
      identity_url: http://identity.youopenstack.com/v2.0/tokens
      compute_name: nova
      protocol: ipv4

      compute_region: RegionOne

      # Configure Openstack authentication credentials
      #
      user: myname
      password: 123456
      # tenant is the project name
      tenant: myproject

      driver: openstack

      # skip SSL certificate validation (default false)
      insecure: false

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

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
      ssh_key_name: test
      ssh_interface: private_ips

The following list explains some of the important properties.


size
    can be one of the options listed in the output of ``nova flavor-list``.

image
    can be one of the options listed in the output of ``nova image-list``.

ssh_key_file
    The SSH private key that the salt-cloud uses to SSH into the VM after its
    first booted in order to execute a command or script. This private key's
    *public key* must be the openstack public key inserted into the
    authorized_key's file of the VM's root user account.

ssh_key_name
    The name of the openstack SSH public key that is inserted into the
    authorized_keys file of the VM's root user account. Prior to using this
    public key, you must use openstack commands or the horizon web UI to load
    that key into the tenant's account. Note that this openstack tenant must be
    the one you defined in the cloud provider.

ssh_interface
    This option allows you to create a VM without a public IP. If this option
    is omitted and the VM does not have a public IP, then the salt-cloud waits
    for a certain period of time and then destroys the VM. With the nova drive,
    private cloud networks can be defined here.

For more information concerning cloud profiles, see :ref:`here
<salt-cloud-profiles>`.


change_password
~~~~~~~~~~~~~~~
If no ssh_key_file is provided, and the server already exists, change_password
will use the api to change the root password of the server so that it can be
bootstrapped.

.. code-block:: yaml

    change_password: True


userdata_file
~~~~~~~~~~~~~
Use `userdata_file` to specify the userdata file to upload for use with
cloud-init if available.

.. code-block:: yaml

    userdata_file: /etc/salt/cloud-init/packages.yml

.. note::
    As of the 2016.11.0 release, this file can be templated, and as of the
    2016.11.4 release, the renderer(s) used can be specified in the cloud
    profile using the ``userdata_renderer`` option. If this option is not set
    in the cloud profile, salt-cloud will fall back to the
    :conf_master:`userdata_renderer` master configuration option.
