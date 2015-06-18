===========================
Getting Started With GoGrid
===========================

GoGrid is a public cloud provider supporting Linux and Windows.


Dependencies
============
* Libcloud >= 0.13.2


Configuration
=============
To use Salt Cloud with GoGrid log into the GoGrid web interface and create an
API key. Do this by clicking on "My Account" and then going to the API Keys
tab.

The ``apikey`` and the ``sharedsecret`` configuration parameters need to be set
in the configuration file to enable interfacing with GoGrid:

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-gogrid-config:
      provider: gogrid
      apikey: asdff7896asdh789
      sharedsecret: saltybacon

.. note::

    A Note about using Map files with GoGrid:

    Due to limitations in the GoGrid API, instances cannot be provisioned in parallel
    with the GoGrid driver. Map files will work with GoGrid, but the ``-P``
    argument should not be used on maps referencing GoGrid instances.


Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~
Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d/`` directory:

.. code-block:: yaml

    gogrid_512:
      provider: my-gogrid-config
      size: 512MB
      image: CentOS 6.2 (64-bit) w/ None

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-gogrid-config
    my-gogrid-config:
        ----------
        gogrid:
            ----------
            512MB:
                ----------
                bandwidth:
                    None
                disk:
                    30
                driver:
                get_uuid:
                id:
                    512MB
                name:
                    512MB
                price:
                    0.095
                ram:
                    512
                uuid:
                    bde1e4d7c3a643536e42a35142c7caac34b060e9
    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-gogrid-config
    my-gogrid-config:
        ----------
        gogrid:
            ----------
            CentOS 6.4 (64-bit) w/ None:
                ----------
                driver:
                extra:
                    ----------
                get_uuid:
                id:
                    18094
                name:
                    CentOS 6.4 (64-bit) w/ None
                uuid:
                    bfd4055389919e01aa6261828a96cf54c8dcc2c4
    ...SNIP...