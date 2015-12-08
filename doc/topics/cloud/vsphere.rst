============================
Getting Started With vSphere
============================

.. note::

    .. deprecated:: Carbon

        The :py:func:`vsphere <salt.cloud.clouds.vsphere>` cloud driver has been
        deprecated in favor of the :py:func:`vmware <salt.cloud.clouds.vmware>`
        cloud driver and will be removed in Salt Carbon. Please refer to
        :doc:`Getting started with VMware </topics/cloud/vmware>` instead to get
        started with the configuration.

VMware vSphere is a management platform for virtual infrastructure and cloud
computing.


Dependencies
============
The vSphere module for Salt Cloud requires the PySphere package, which is
available at PyPI:

https://pypi.python.org/pypi/pysphere

This package can be installed using `pip` or `easy_install`:

.. code-block:: bash

  # pip install pysphere
  # easy_install pysphere


Configuration
=============
Set up the cloud config at ``/etc/salt/cloud.providers`` or in the
``/etc/salt/cloud.providers.d/`` directory:

.. code-block:: yaml

    my-vsphere-config:
      driver: vsphere
      # Set the vSphere access credentials
      user: marco
      password: polo
      # Set the URL of your vSphere server
      url: 'vsphere.example.com'

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
vSphere uses a Managed Object Reference to identify objects located in vCenter.
The MOR ID's are used when configuring a vSphere cloud profile. Use the
following reference when locating the MOR's for the cloud profile.

http://kb.vmware.com/selfservice/microsites/search.do?cmd=displayKC&docType=kc&externalId=1017126&sliceId=1&docTypeID=DT_KB_1_1&dialogID=520386078&stateId=1%200%20520388386

Set up an initial profile at ``/etc/salt/cloud.profiles`` or in the
``/etc/salt/cloud.profiles.d`` directory:

.. code-block:: yaml

    vsphere-centos:
      provider: my-vsphere-config
      image: centos
      # Optional
      datastore: datastore-15
      resourcepool: resgroup-8
      folder: salt-cloud
      host: host-9
      template: False


provider
--------
Enter the name that was specified when the cloud provider profile was created.

image
-----
Images available to build an instance can be found using the `--list-images`
option:

.. code-block:: bash

    # salt-cloud --list-images my-vsphere-config

datastore
---------
The MOR of the datastore where the virtual machine should be located. If not
specified, the current datastore is used.

resourcepool
------------
The MOR of the resourcepool to be used for the new vm. If not set, it will use
the same resourcepool as the original vm.

folder
------
Name of the folder that will contain the new VM. If not set, the VM will be
added to the folder the original VM belongs to.

host
----
The MOR of the host where the vm should be registered.

  If not specified:
    * if resourcepool is not specified, the current host is used.
    * if resourcepool is specified, and the target pool represents a
      stand-alone host, the host is used.
    * if resourcepool is specified, and the target pool represents a
      DRS-enabled cluster, a host selected by DRS is used.
    * if resourcepool is specified, and the target pool represents a
      cluster without DRS enabled, an InvalidArgument exception will be thrown.

template
--------
Specifies whether or not the new virtual machine should be marked as a
template. Default is False.
