=================================
Getting Started With DigitalOcean
=================================

DigitalOcean is a public cloud provider that specializes in Linux instances.


Configuration
=============
Starting in Salt 2015.5.0, a new DigitalOcean driver was added to Salt Cloud to support
DigitalOcean's new API, APIv2. The original driver, referred to ``digital_ocean`` will
be supported throughout the 2015.5.x releases of Salt, but will then be removed in Salt
Beryllium in favor of the APIv2 driver, ``digital_ocean_v2``. The following documentation
is relevant to the new driver, ``digital_ocean_v2``. To see documentation related to the
original ``digital_ocean`` driver, please see the
:mod:`DigitalOcean Salt Cloud Driver <salt.cloud.clouds.digital_ocean>`

.. note::

    When Salt Beryllium is released, the original ``digital_ocean`` driver will no longer
    be supported and the ``digital_ocean_v2`` driver will become the ``digital_ocean``
    driver.

Using Salt for DigitalOcean requires a ``personal_access_token``, an ``ssh_key_file``,
and at least one SSH key name in ``ssh_key_names``. More can be added by separating each key
with a comma. The ``personal_access_token`` can be found in the DigitalOcean web interface
in the "Apps & API" section. The SSH key name can be found under the "SSH Keys" section.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-digitalocean-config:
      provider: digital_ocean
      personal_access_token: xxx
      ssh_key_file: /path/to/ssh/key/file
      ssh_key_names: my-key-name,my-key-name-2
      location: New York 1


Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    digitalocean-ubuntu:
        provider: my-digitalocean-config
        image: Ubuntu 14.04 x32
        size: 512MB
        location: New York 1
        private_networking: True
        backups_enabled: True
        ipv6: True

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations my-digitalocean-config
    my-digitalocean-config:
        ----------
        digital_ocean:
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
        digital_ocean:
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
        digital_ocean:
            ----------
            Arch Linux 2013.05 x64:
                ----------
                distribution:
                    Arch Linux
                id:
                    350424
                name:
                    Arch Linux 2013.05 x64
                public:
                    True
                slug:
                    None
    ...SNIP...

.. note::

    DigitalOcean's concept of ``Applications`` is nothing more than a
    pre-configured instance (same as a normal Droplet). You will find examples
    such ``Docker 0.7 Ubuntu 13.04 x64`` and ``Wordpress on Ubuntu 12.10``
    when using the ``--list-images`` option. These names can be used just like
    the rest of the standard instances when specifying an image in the cloud
    profile configuration.

.. note::

    If your domain's DNS is managed with DigitalOcean, you can automatically
    create A-records for newly created droplets. Use ``create_dns_record: True``
    in your config to enable this. Add ``delete_dns_record: True`` to also
    delete records when a droplet is destroyed.

.. note::

    Additional documentation is available from `DigitalOcean <https://www.digitalocean.com/community/articles/automated-provisioning-of-digitalocean-cloud-servers-with-salt-cloud-on-ubuntu-12-04>`_.