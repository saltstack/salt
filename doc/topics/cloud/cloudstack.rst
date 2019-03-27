===============================
Getting Started with CloudStack
===============================

CloudStack is one the most popular cloud projects. It's an open source project
to build public and/or private clouds. You can use Salt Cloud to launch
CloudStack instances.


Dependencies
============
* Libcloud >= 0.13.2

Configuration
=============
Using Salt for CloudStack, requires an ``API key`` and a ``secret key`` along with the API address endpoint information.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    exoscale:
      driver: cloudstack
      host: api.exoscale.com
      path: /compute
      apikey: EXOAPIKEY
      secretkey: EXOSECRETKEYINYOURACCOUNT

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

    exoscale-ubuntu:
      provider: exoscale-config
      image: Linux Ubuntu 18.04
      size: Small
      location: ch-gva-2
      ssh_username: ubuntu

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations exoscale-config
    exoscale:
        ----------
        cloudstack:
            ----------
            ch-dk-2:
                ----------
                country:
                    Unknown
                driver:
                id:
                    91e5e9e4-c9ed-4b76-bee4-427004b3baf9
                name:
                    ch-dk-2
            ch-gva-2:
                ----------
                country:
                    Unknown
                driver:
                id:
                    1128bd56-b4d9-4ac6-a7b9-c715b187ce11
                name:
                    ch-gva-2

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes exoscale
    exoscale:
        ----------
        cloudstack:
            ----------
            Extra-large:
                ----------
                bandwidth:
                    0
                disk:
                    0
                driver:
                extra:
                    ----------
                    cpu:
                        4
                get_uuid:
                id:
                    350dc5ea-fe6d-42ba-b6c0-efb8b75617ad
                name:
                    Extra-large
                price:
                    0
                ram:
                    16384
                uuid:
                    edb4cd4ae14bbf152d451b30c4b417ab095a5bfe
    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images exoscale
    exoscale:
        ----------
        cloudstack:
            ----------
            Linux CentOS 6.6 64-bit:
                ----------
                driver:
                extra:
                    ----------
                    displaytext:
                        Linux CentOS 6.6 64-bit 10G Disk (2014-12-01-bac8e0)
                    format:
                        QCOW2
                    hypervisor:
                        KVM
                    os:
                        Other PV (64-bit)
                    size:
                        10737418240
                get_uuid:
                id:
                    aa69ae64-1ea9-40af-8824-c2c3344e8d7c
                name:
                    Linux CentOS 6.6 64-bit
                uuid:
                    f26b4f54ec8591abdb6b5feb3b58f720aa438fee
    ...SNIP...

CloudStack specific settings
============================

securitygroup
~~~~~~~~~~~~~~
.. versionadded:: 2017.7.0

You can specify a list of security groups (by name or id) that should be
assigned to the VM:

.. code-block:: yaml

    exoscale:
      provider: cloudstack
      securitygroup:
        - default
        - salt-master

