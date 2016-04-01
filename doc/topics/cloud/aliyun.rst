===============================
Getting Started With Aliyun ECS
===============================

The Aliyun ECS (Elastic Computer Service) is one of the most popular public
cloud hosts in China. This cloud host can be used to manage aliyun
instance using salt-cloud.

http://www.aliyun.com/


Dependencies
============
This driver requires the Python ``requests`` library to be installed.


Configuration
=============
Using Salt for Aliyun ECS requires aliyun access key id and key secret.
These can be found in the aliyun web interface, in the "User Center" section,
under "My Service" tab.


.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-aliyun-config:
      # aliyun Access Key ID
      id: wDGEwGregedg3435gDgxd
      # aliyun Access Key Secret
      key: GDd45t43RDBTrkkkg43934t34qT43t4dgegerGEgg
      location: cn-qingdao
      driver: aliyun

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

    aliyun_centos:
        provider: my-aliyun-config
        size: ecs.t1.small
        location: cn-qingdao
        securitygroup: G1989096784427999
        image: centos6u3_64_20G_aliaegis_20130816.vhd


Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes my-aliyun-config
    my-aliyun-config:
        ----------
        aliyun:
            ----------
            ecs.c1.large:
                ----------
                CpuCoreCount:
                    8
                InstanceTypeId:
                    ecs.c1.large
                MemorySize:
                    16.0

    ...SNIP...

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images my-aliyun-config
    my-aliyun-config:
        ----------
        aliyun:
            ----------
            centos5u8_64_20G_aliaegis_20131231.vhd:
                ----------
                Architecture:
                    x86_64
                Description:

                ImageId:
                    centos5u8_64_20G_aliaegis_20131231.vhd
                ImageName:
                    CentOS 5.8 64位
                ImageOwnerAlias:
                    system
                ImageVersion:
                    1.0
                OSName:
                    CentOS  5.8 64位
                Platform:
                    CENTOS5
                Size:
                    20
                Visibility:
                    public
    ...SNIP...

Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    my-aliyun-config:
        ----------
        aliyun:
            ----------
            cn-beijing:
                ----------
                LocalName:
                    北京
                RegionId:
                    cn-beijing
            cn-hangzhou:
                ----------
                LocalName:
                    杭州
                RegionId:
                    cn-hangzhou
            cn-hongkong:
                ----------
                LocalName:
                    香港
                RegionId:
                    cn-hongkong
            cn-qingdao:
                ----------
                LocalName:
                    青岛
                RegionId:
                    cn-qingdao

Security Group can be obtained using the ``-f list_securitygroup`` option
for the ``salt-cloud`` command:

.. code-block:: bash

    # salt-cloud --location=cn-qingdao -f list_securitygroup my-aliyun-config
    my-aliyun-config:
        ----------
        aliyun:
            ----------
            G1989096784427999:
                ----------
                Description:
                    G1989096784427999
                SecurityGroupId:
                    G1989096784427999

.. note::

    Aliyun ECS REST API documentation is available from `Aliyun ECS API <http://help.aliyun.com/list/11113464.html?spm=5176.7224429.1997282881.55.J9XhVL>`_.
