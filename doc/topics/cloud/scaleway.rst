=============================
Getting Started With Scaleway
=============================

Scaleway is the first IaaS host worldwide to offer an ARM based cloud. It’s the ideal platform for horizontal scaling with BareMetal SSD servers. The solution provides on demand resources: it comes with on-demand SSD storage, movable IPs , images, security group and an Object Storage solution. https://scaleway.com

Configuration
=============
Using Salt for Scaleway, requires an ``access key`` and an ``API token``. ``API tokens`` are unique identifiers associated with your Scaleway account.
To retrieve your ``access key`` and ``API token``, log-in to the Scaleway control panel, open the pull-down menu on your account name and click on "My Credentials" link.

If you do not have API token you can create one by clicking the "Create New Token" button on the right corner.

.. code-block:: yaml

    # Note: This example is for /etc/salt/cloud.providers or any file in the
    # /etc/salt/cloud.providers.d/ directory.

    my-scaleway-config:
      access_key: 15cf404d-4560-41b1-9a0c-21c3d5c4ff1f
      token: a7347ec8-5de1-4024-a5e3-24b77d1ba91d
      driver: scaleway

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

Set up an initial profile at /etc/salt/cloud.profiles or in the /etc/salt/cloud.profiles.d/ directory:

.. code-block:: yaml

    scaleway-ubuntu:
      provider: my-scaleway-config
      image: Ubuntu Trusty (14.04 LTS)


Images can be obtained using the ``--list-images`` option for the ``salt-cloud`` command:

.. code-block:: console

    #salt-cloud --list-images my-scaleway-config
    my-scaleway-config:
      ----------
      scaleway:
          ----------
          069fd876-eb04-44ab-a9cd-47e2fa3e5309:
              ----------
              arch:
                  arm
              creation_date:
                  2015-03-12T09:35:45.764477+00:00
              default_bootscript:
                  {u'kernel': {u'dtb': u'', u'title': u'Pimouss 3.2.34-30-std', u'id': u'cfda4308-cd6f-4e51-9744-905fc0da370f', u'path': u'kernel/pimouss-uImage-3.2.34-30-std'}, u'title': u'3.2.34-std #30 (stable)', u'id': u'c5af0215-2516-4316-befc-5da1cfad609c', u'initrd': {u'path': u'initrd/c1-uInitrd', u'id': u'1be14b1b-e24c-48e5-b0b6-7ba452e42b92', u'title': u'C1 initrd'}, u'bootcmdargs': {u'id': u'd22c4dde-e5a4-47ad-abb9-d23b54d542ff', u'value': u'ip=dhcp boot=local root=/dev/nbd0 USE_XNBD=1 nbd.max_parts=8'}, u'organization': u'11111111-1111-4111-8111-111111111111', u'public': True}
              extra_volumes:
                  []
              id:
                  069fd876-eb04-44ab-a9cd-47e2fa3e5309
              modification_date:
                  2015-04-24T12:02:16.820256+00:00
              name:
                  Ubuntu Vivid (15.04)
              organization:
                  a283af0b-d13e-42e1-a43f-855ffbf281ab
              public:
                  True
              root_volume:
                  {u'name': u'distrib-ubuntu-vivid-2015-03-12_10:32-snapshot', u'id': u'a6d02e63-8dee-4bce-b627-b21730f35a05', u'volume_type': u'l_ssd', u'size': 50000000000L}
    ...


Execute a query and return all information about the nodes running on configured cloud providers using the ``-Q`` option for the ``salt-cloud`` command:

.. code-block:: console

    # salt-cloud -F
    [INFO    ] salt-cloud starting
    [INFO    ] Starting new HTTPS connection (1): api.scaleway.com
    my-scaleway-config:
      ----------
      scaleway:
          ----------
          salt-manager:
              ----------
              creation_date:
                  2015-06-03T08:17:38.818068+00:00
              hostname:
                  salt-manager
    ...

.. note::

    Additional documentation about Scaleway can be found at `<https://www.scaleway.com/docs>`_.
