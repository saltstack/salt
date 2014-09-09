==================================
Getting Started With DigitalOcean
==================================

DigitalOcean is a public cloud provider that specializes in Linux instances.


Configuration
=============
Using Salt for DigitalOcean requires a client_key, an api_key, an ssh_key_file,
and an ssh_key_name. The client_key and api_key can be found in the Digital
Ocean web interface, in the "My Settings" section, under the API Access tab.
The ssh_key_name can be found under the "SSH Keys" section. 

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-digitalocean-config:
      provider: digital_ocean
      client_key: wFGEwgregeqw3435gDger
      api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg
      ssh_key_file: /path/to/ssh/key/file
      ssh_key_name: my-key-name
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

    Additional documentation is available from `DigitalOcean <https://www.digitalocean.com/community/articles/automated-provisioning-of-digitalocean-cloud-servers-with-salt-cloud-on-ubuntu-12-04>`_.
