=================================
Getting Started With Digtal Ocean
=================================

Digital Ocean is a public cloud provider that specializes Linux instances.


Dependencies
============
The Digital Ocean driver requires no special dependencies outside of Salt.


Configuration
=============
Using Salt for Digital Ocean requires a client_key and an api_key. These can be
found in the Digital Ocean web interface, in the "My Settings" section, under
the API Access tab.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-digitalocean-config:
      provider: digital_ocean
      client_key: wFGEwgregeqw3435gDger
      api_key: GDE43t43REGTrkilg43934t34qT43t4dgegerGEgg
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
        image: Ubuntu 12.10 x64
        size: 512MB
        location: New York 1

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
