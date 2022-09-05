=========================================
Getting Started With Dimension Data Cloud
=========================================

Dimension Data are a global IT Services company and form part of the NTT Group.
Dimension Data provide IT-as-a-Service to customers around the globe on their
cloud platform (Compute as a Service). The CaaS service is available either on
one of the public cloud instances or as a private instance on premises.

http://cloud.dimensiondata.com/

CaaS has its own non-standard API , SaltStack provides a wrapper on top of this
API with common methods with other IaaS solutions and Public cloud providers.
Therefore, you can use the Dimension Data module to communicate with both the
public and private clouds.


Dependencies
============

This driver requires the Python ``apache-libcloud`` and ``netaddr`` library to be installed.


Configuration
=============

When you instantiate a driver you need to pass the following arguments to the
driver constructor:

* ``user_id`` - Your Dimension Data Cloud username
* ``key`` - Your Dimension Data Cloud password
* ``region`` - The region key, one of the possible region keys

Possible regions:

* ``dd-na`` : Dimension Data North America (USA)
* ``dd-eu`` : Dimension Data Europe
* ``dd-af`` : Dimension Data Africa
* ``dd-au`` : Dimension Data Australia
* ``dd-latam`` : Dimension Data Latin America
* ``dd-ap`` : Dimension Data Asia Pacific
* ``dd-canada`` : Dimension Data Canada region

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-dimensiondata-config:
      user_id: my_username
      key: myPassword!
      region: dd-na
      driver: dimensiondata

.. note::

    In version 2015.8.0, the ``provider`` parameter in cloud provider
    definitions was renamed to ``driver``. This change was made to avoid
    confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the
    Salt cloud module that provides the underlying functionality to connect to
    a cloud host, while cloud profiles continue to use ``provider`` to refer to
    provider configurations that you define.

Profiles
========

Cloud Profiles
~~~~~~~~~~~~~~

Dimension Data images have an inbuilt size configuration, there is no list of sizes (although, if the
command --list-sizes is run a default will be returned).

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: console

    # salt-cloud --list-images my-dimensiondata-config
    my-dimensiondata-config:
    ----------
    dimensiondata:
        ----------
        CSfM SharePoint 2013 Trial:
            ----------
            driver:
            extra:
                ----------
                OS_displayName:
                    WIN2012R2S/64
                OS_type:
                    None
                cpu:
                created:
                    2015-03-19T18:36:06.000Z
                description:
                    Windows 2012 R2 Standard 64-bit installed with SharePoint 2013 and Visual Studio 2013 Pro (Trial Version)
                location:
                memoryGb:
                    12
                osImageKey:
                    T-WIN-2012R2-STD-SP2013-VS2013-64-4-12-100
            get_uuid:
            id:
                0df4677e-d380-4e9b-9469-b529ee0214c5
            name:
                CSfM SharePoint 2013 Trial
            uuid:
                28c077f1be970ee904541407b377e3ff87a9ac69
        CentOS 5 32-bit 2 CPU:
            ----------
            driver:
            extra:
                ----------
                OS_displayName:
                    CENTOS5/32
                OS_type:
                    None
                cpu:
                created:
                    2015-10-21T14:52:29.000Z
                description:
                    CentOS Release 5.11 32-bit
                location:
                memoryGb:
                    4
                osImageKey:
                    T-CENT-5-32-2-4-10
            get_uuid:
            id:
                a8046bd1-04ea-4668-bf32-bf8d5540faed
            name:
                CentOS 5 32-bit 2 CPU
            uuid:
                4d7dd59929fed6f4228db861b609da64997773a7

    ...SNIP...

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    my-dimensiondata-config:
        ----------
        dimensiondata:
            ----------
            Australia - Melbourne:
                ----------
                country:
                    Australia
                driver:
                id:
                    AU2
                name:
                    Australia - Melbourne
            Australia - Melbourne MCP2:
                ----------
                country:
                    Australia
                driver:
                id:
                    AU10
                name:
                    Australia - Melbourne MCP2
            Australia - Sydney:
                ----------
                country:
                    Australia
                driver:
                id:
                    AU1
                name:
                    Australia - Sydney
            Australia - Sydney MCP2:
                ----------
                country:
                    Australia
                driver:
                id:
                    AU9
                name:
                    Australia - Sydney MCP2
            New Zealand:
                ----------
                country:
                    New Zealand
                driver:
                id:
                    AU8
                name:
                    New Zealand
            New_Zealand:
                ----------
                country:
                    New Zealand
                driver:
                id:
                    AU11
                name:
                    New_Zealand


.. note::

    Dimension Data Cloud REST API documentation is available from `Dimension Data MCP 2 <https://community.opsourcecloud.net/Browse.jsp?id=e5b1a66815188ad439f76183b401f026>`_.
