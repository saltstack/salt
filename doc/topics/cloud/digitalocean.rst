=================================
Getting Started With DigitalOcean
=================================

DigitalOcean is a public cloud host that specializes in Linux instances.


Configuration
=============
Using Salt for DigitalOcean requires a ``personal_access_token``, an ``ssh_key_file``,
and at least one SSH key name in ``ssh_key_names``. More ``ssh_key_names`` can be added
by separating each key with a comma. The ``personal_access_token`` can be found in the
DigitalOcean web interface in the "Apps & API" section. The SSH key name can be found
under the "SSH Keys" section.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-digitalocean-config:
      driver: digitalocean
      personal_access_token: xxx
      ssh_key_file: /path/to/ssh/key/file
      ssh_key_names: my-key-name,my-key-name-2
      location: New York 1

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.

Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    digitalocean-ubuntu:
      provider: my-digitalocean-config
      image: 14.04 x64
      size: 512MB
      location: New York 1
      private_networking: True
      backups_enabled: True
      ipv6: True
      create_dns_record: True
      userdata_file: /etc/salt/cloud.userdata.d/setup
      tags:
        - tag1
        - tag2
        - tag3

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations my-digitalocean-config
    my-digitalocean-config:
        ----------
        digitalocean:
            ----------
            Amsterdam 1:
                ----------
                available:
                    False
                features:
                    [u'backups']
                name:
                    Amsterdam 1
                sizes:
                    []
                slug:
                    ams1
    ...SNIP...

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-digitalocean-config
    my-digitalocean-config:
        ----------
        digitalocean:
            ----------
            512MB:
                ----------
                cost_per_hour:
                    0.00744
                cost_per_month:
                    5.0
                cpu:
                    1
                disk:
                    20
                id:
                    66
                memory:
                    512
                name:
                    512MB
                slug:
                    None
    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-digitalocean-config
    my-digitalocean-config:
        ----------
        digitalocean:
            ----------
            10.1:
                ----------
                created_at:
                    2015-01-20T20:04:34Z
                distribution:
                    FreeBSD
                id:
                    10144573
                min_disk_size:
                    20
                name:
                    10.1
                public:
                    True
    ...SNIP...


Profile Specifics:
------------------

ssh_username
------------

If using a FreeBSD image from DigitalOcean, you'll need to set the ``ssh_username``
setting to ``freebsd`` in your profile configuration.

.. code-block:: yaml

    digitalocean-freebsd:
      provider: my-digitalocean-config
      image: 10.2
      size: 512MB
      ssh_username: freebsd

userdata_file
~~~~~~~~~~~~~

.. versionadded:: 2016.11.6

Use `userdata_file` to specify the userdata file to upload for use with
cloud-init if available.

.. code-block:: yaml

    my-openstack-config:
      # Pass userdata to the instance to be created
      userdata_file: /etc/salt/cloud-init/packages.yml

.. code-block:: yaml

    my-do-config:
      # Pass userdata to the instance to be created
      userdata_file: /etc/salt/cloud-init/packages.yml
      userdata_template: jinja

If no ``userdata_template`` is set in the cloud profile, then the master
configuration will be checked for a :conf_master:`userdata_template` value.
If this is not set, then no templating will be performed on the
userdata_file.

To disable templating in a cloud profile when a
:conf_master:`userdata_template` has been set in the master configuration
file, simply set ``userdata_template`` to ``False`` in the cloud profile:

.. code-block:: yaml

    my-do-config:
      # Pass userdata to the instance to be created
      userdata_file: /etc/salt/cloud-init/packages.yml
      userdata_template: False


Miscellaneous Information
=========================

.. note::

    DigitalOcean's concept of ``Applications`` is nothing more than a
    pre-configured instance (same as a normal Droplet). You will find examples
    such ``Docker 0.7 Ubuntu 13.04 x64`` and ``Wordpress on Ubuntu 12.10``
    when using the ``--list-images`` option. These names can be used just like
    the rest of the standard instances when specifying an image in the cloud
    profile configuration.

.. note::

    If your domain's DNS is managed with DigitalOcean, and your minion name
    matches your DigitalOcean managed DNS domain, you can automatically create
    A and AAA records for newly created droplets. Use ``create_dns_record: True``
    in your config to enable this. Adding ``delete_dns_record: True`` to also
    delete records when a droplet is destroyed is optional. Due to limitations
    in salt-cloud design, the destroy code does not have access to the VM config
    data. WHETHER YOU ADD ``create_dns_record: True`` OR NOT, salt-cloud WILL
    attempt to delete your DNS records if the minion name matches. This will
    prevent advertising any recycled IP addresses for destroyed minions.

.. note::

   If you need to perform the bootstrap using the local interface for droplets,
   this can be done by setting ``ssh_interface: private`` in your config. By
   default the salt-cloud script would run on the public interface however if firewall
   is preventing the connection to the Droplet over the public interface you might need
   to set this option to connect via private interface. Also, to use this feature
   ``private_networking: True`` must be set in the config.

.. note::

    Additional documentation is available from `DigitalOcean <https://www.digitalocean.com/community/tutorials/automated-provisioning-of-digitalocean-cloud-servers-with-salt-cloud-on-ubuntu-12-04>`_.
