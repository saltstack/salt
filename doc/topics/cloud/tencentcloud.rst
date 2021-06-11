==================================
Getting Started With Tencent Cloud
==================================

Tencent Cloud is a secure, reliable and high-performance cloud compute service
provided by Tencent. It is the 2nd largest Cloud Provider in China.


Dependencies
============
The Tencent Cloud driver for Salt Cloud requires the ``tencentcloud-sdk-python`` package,
which is available at PyPI:

https://pypi.org/project/tencentcloud-sdk-python/

This package can be installed using ``pip`` or ``easy_install``:

.. code-block:: bash

  # pip install tencentcloud-sdk-python
  # easy_install tencentcloud-sdk-python


Provider Configuration
======================
To use this module, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/*.conf``:

.. code-block:: yaml

    my-tencentcloud-config:
      driver: tencentcloud
      # Tencent Cloud Secret Id
      id: AKIDA64pOio9BMemkApzevX0HS169S4b750A
      # Tencent Cloud Secret Key
      key: 8r2xmPn0C5FDvRAlmcJimiTZKVRsk260
      # Tencent Cloud Region
      location: ap-guangzhou

Configuration Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

driver
------
**Required**. ``tencentcloud`` to use this module.

id
--
**Required**. Your Tencent Cloud secret id.

key
---
**Required**. Your Tencent Cloud secret key.

location
--------
**Optional**. If this value is not specified, the default is ``ap-guangzhou``.
Available locations can be found using the ``--list-locations`` option:

.. code-block:: bash

    # salt-cloud --list-location my-tencentcloud-config


Profile Configuration
=====================

Tencent Cloud profiles require a ``provider``, ``availability_zone``, ``image`` and ``size``.
Set up an initial profile at ``/etc/salt/cloud.profiles`` or ``/etc/salt/cloud.profiles.d/*.conf``:

.. code-block:: yaml

    tencentcloud-guangzhou-s1sm1:
        provider: my-tencentcloud-config
        availability_zone: ap-guangzhou-3
        image: img-31tjrtph
        size: S1.SMALL1
        allocate_public_ip: True
        internet_max_bandwidth_out: 1
        password: '153e41ec96140152'
        securitygroups:
            - sg-5e90804b

Configuration Parameters
~~~~~~~~~~~~~~~~~~~~~~~~

provider
--------
**Required**. Name of entry in ``salt/cloud.providers.d/???`` file.

availability_zone
-----------------
**Required**. The availability zone that the instance is located in.
Available zones can be found using the ``list_availability_zones`` function:

.. code-block:: bash

    # salt-cloud -f list_availability_zones my-tencentcloud-config

image
-----
**Required**. The image id to use for the instance.
Available images can be found using the ``--list-images`` option:

.. code-block:: bash

    # salt-cloud --list-images my-tencentcloud-config

size
----
**Required**. Instance type for instance can be found using the ``--list-sizes`` option.

.. code-block:: bash

    # salt-cloud --list-sizes my-tencentcloud-config

securitygroups
--------------
**Optional**. A list of security group ids to associate with.
Available security group ids can be found using the ``list_securitygroups`` function:

.. code-block:: bash

    # salt-cloud -f list_securitygroups my-tencentcloud-config

Multiple security groups are supported:

.. code-block:: yaml

    tencentcloud-guangzhou-s1sm1:
        securitygroups:
            - sg-5e90804b
            - sg-8kpynf2t

hostname
--------
**Optional**. The hostname of the instance.

instance_charge_type
--------------------
**Optional**. The charge type of the instance. Valid values are ``PREPAID``,
``POSTPAID_BY_HOUR`` and ``SPOTPAID``. The default is ``POSTPAID_BY_HOUR``.

instance_charge_type_prepaid_renew_flag
---------------------------------------
**Optional**. When enabled, the instance will be renew automatically
when it reaches the end of the prepaid tenancy.
Valid values are ``NOTIFY_AND_AUTO_RENEW``, ``NOTIFY_AND_MANUAL_RENEW`` and ``DISABLE_NOTIFY_AND_MANUAL_RENEW``.

.. note::

    This value is only used when ``instance_charge_type`` is set to ``PREPAID``.

instance_charge_type_prepaid_period
-----------------------------------
**Optional**. The tenancy time in months of the prepaid instance,
Valid values are ``1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 24, 36``.

.. note::

    This value is only used when ``instance_charge_type`` is set to ``PREPAID``.

allocate_public_ip
------------------
**Optional**. Associate a public ip address with an instance
in a VPC or Classic. Boolean value, default is ``false``.

internet_max_bandwidth_out
--------------------------
**Optional**. Maximum outgoing bandwidth to the public network, measured in Mbps (Mega bits per second).
Value range: ``[0, 100]``. If this value is not specified, the default is ``0`` Mbps.

internet_charge_type
--------------------
**Optional**. Internet charge type of the instance. Valid values are ``BANDWIDTH_PREPAID``,
``TRAFFIC_POSTPAID_BY_HOUR``, ``BANDWIDTH_POSTPAID_BY_HOUR`` and ``BANDWIDTH_PACKAGE``.
The default is ``TRAFFIC_POSTPAID_BY_HOUR``.

key_name
--------
**Optional**. The key pair to use for the instance, for example ``skey-16jig7tx``.

password
--------
**Optional**. Login password for the instance.

private_ip
----------
**Optional**. The private ip to be assigned to this instance,
must be in the provided subnet and available.

project_id
----------
**Optional**. The project this instance belongs to, defaults to ``0``.

vpc_id
------
**Optional**. The id of a VPC network.
If you want to create instances in a VPC network, this parameter must be set.

subnet_id
---------
**Optional**. The id of a VPC subnet.
If you want to create instances in VPC network, this parameter must be set.

system_disk_size
----------------
**Optional**. Size of the system disk.
Value range: ``[50, 1000]``, and unit is ``GB``. Default is ``50`` GB.

system_disk_type
----------------
**Optional**. Type of the system disk.
Valid values are ``CLOUD_BASIC``, ``CLOUD_SSD`` and ``CLOUD_PREMIUM``, default value is ``CLOUD_BASIC``.


Actions
=======
The following actions are supported by the Tencent Cloud Salt Cloud driver.

show_instance
~~~~~~~~~~~~~
This action is a thin wrapper around ``--full-query``, which displays details on a
single instance only. In an environment with several machines, this will save a
user from having to sort through all instance data, just to examine a single
instance.

.. code-block:: bash

    $ salt-cloud -a show_instance myinstance

show_disk
~~~~~~~~~
Return disk details about a specific instance.

.. code-block:: bash

    $ salt-cloud -a show_disk myinstance

destroy
~~~~~~~
Destroy a Tencent Cloud instance.

.. code-block:: bash

    $ salt-cloud -a destroy myinstance

start
~~~~~
Start a Tencent Cloud instance.

.. code-block:: bash

    $ salt-cloud -a start myinstance

stop
~~~~
Stop a Tencent Cloud instance.

.. code-block:: bash

    $ salt-cloud -a stop myinstance

reboot
~~~~~~
Reboot a Tencent Cloud instance.

.. code-block:: bash

    $ salt-cloud -a reboot myinstance


Functions
=========
The following functions are currently supported by the Tencent Cloud Salt Cloud driver.

list_securitygroups
~~~~~~~~~~~~~~~~~~~
Lists all Tencent Cloud security groups in current region.

.. code-block:: bash

    $ salt-cloud -f list_securitygroups my-tencentcloud-config

list_availability_zones
~~~~~~~~~~~~~~~~~~~~~~~
Lists all Tencent Cloud availability zones in current region.

.. code-block:: bash

    $ salt-cloud -f list_availability_zones my-tencentcloud-config

list_custom_images
~~~~~~~~~~~~~~~~~~
Lists any custom images associated with the account. These images can
be used to create a new instance.

.. code-block:: bash

    $ salt-cloud -f list_custom_images my-tencentcloud-config

show_image
~~~~~~~~~~
Return details about a specific image. This image can be used
to create a new instance.

.. code-block:: bash

    $ salt-cloud -f show_image tencentcloud image=img-31tjrtph
