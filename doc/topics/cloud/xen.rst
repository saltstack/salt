===========================
Getting Started With Xen
===========================

The Xen cloud driver works with Citrix XenServer.

It can be used with a single XenServer or a XenServer resource pool.

Setup Dependencies
==================

This driver requires a copy of the freely available ``XenAPI.py`` Python module.

Information about the Xen API Python module in the XenServer SDK
can be found at https://pypi.org/project/XenAPI/


Place a copy of this module on your system. For example, it can
be placed in the `site packages` location on your system.

The location of `site packages` can be determined by running:

.. code-block:: bash

    python -m site --user-site


Provider Configuration
======================

Xen requires login credentials to a XenServer.

Set up the provider cloud configuration file at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/*.conf``.

.. code-block:: yaml

        # /etc/salt/cloud.providers.d/myxen.conf
        myxen:
          driver: xen
          url: https://10.0.0.120
          user: root
          password: p@ssw0rd

url:
  The ``url`` option supports both ``http`` and ``https`` uri prefixes.

user:
  A valid user id to login to the XenServer host.

password:
  The associated password for the user.

.. note::
    .. versionchanged:: 2015.8.0

    The ``provider`` parameter in cloud provider definitions was renamed to ``driver``. This
    change was made to avoid confusion with the ``provider`` parameter that is used in cloud profile
    definitions. Cloud provider definitions now use ``driver`` to refer to the Salt cloud module that
    provides the underlying functionality to connect to a cloud host, while cloud profiles continue
    to use ``provider`` to refer to provider configurations that you define.


Profile Configuration
=====================

Xen profiles require a ``provider`` and  ``image``.

provider:
  This will be the name of your defined provider.

image:
  The name of the VM template used to clone or copy.

clone:
  The default behavior is to clone a template or VM. This is very fast,
  but requires the source template or VM to be in the same storage
  repository of the new target system. If the source and target are in
  different storage repositories then you must copy the source and not
  clone it by setting ``clone: False``.

deploy:
  The provisioning process will attempt to install the Salt minion
  service on the new target system by default. This will require login
  credentials for Salt cloud to login via ssh to it.  The ``user`` and
  ``password`` options are required.  If ``deploy`` is set to ``False``
  then these options are not needed.

resource_pool:
  The name of the resource pool used for this profile.

storage_repo:
  The name of the storage repository for the target system.

ipv4_cidr:
  If template is Windows, and running guest tools then a static
  ip address can be set.

ipv4_gw:
  If template is Windows, and running guest tools then a gateway
  can be set.

Set up an initial profile
at ``/etc/salt/cloud.profiles`` or in the ``/etc/salt/cloud.profiles.d/`` directory:


.. code-block:: yaml

    # file: /etc/salt/cloud.profiles.d/xenprofiles.conf
    sles:
      provider: myxen
      deploy: False
      image: sles12sp2-template

    suse:
      user: root
      password: p@ssw0rd
      provider: myxen
      image: opensuseleap42_2-template
      storage_repo: 'Local storage'
      clone: False
      minion:
        master: 10.0.0.20

    w2k12:
      provider: myxen
      image: w2k12svr-template
      clone: True
      userdata_file: /srv/salt/win/files/windows-firewall.ps1
      win_installer: /srv/salt/win/files/Salt-Minion-2016.11.3-AMD64-Setup.exe
      win_username: Administrator
      win_password: p@ssw0rd
      use_winrm: False
      ipv4_cidr: 10.0.0.215/24
      ipv4_gw: 10.0.0.1
      minion:
        master: 10.0.0.21

The first example will create a clone of the sles12sp2-template in the
same storage repository without deploying the Salt minion.

The second example will make a copy of the image and deploy a new
suse VM with the Salt minion installed.

The third example will create a clone of the Windows 2012 template
and deploy the Salt minion.


The profile can be used with a salt command:

.. code-block:: bash

    salt-cloud -p suse  xenvm02

This will create an salt minion instance named ``xenvm02`` in Xen. If the command was
executed on the salt-master, its Salt key will automatically be signed on the master.

Once the instance has been created with a salt-minion installed, connectivity to
it can be verified with Salt:

.. code-block:: bash

    salt xenvm02 test.version


Listing Sizes
-------------

Sizes can be obtained using the ``--list-sizes`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-sizes myxen

.. note:: Since size information is build in a template this command
          is not implemented.

Listing Images
--------------

Images can be obtained using the ``--list-images`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-images myxen

This command will return a list of templates with details.


Listing Locations
-----------------
Locations can be obtained using the ``--list-locations`` option for the ``salt-cloud``
command:

.. code-block:: bash

    # salt-cloud --list-locations myxen

Returns a list of resource pools.
