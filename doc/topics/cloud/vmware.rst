===================================
Getting Started With VMware vSphere
===================================

.. versionadded:: Beryllium

**Author**: Nitin Madhok <nmadhok@clemson.edu>

VMware vSphere is a server virtualization platform for building cloud
infrastructure.

Dependencies
============
The vmware module for Salt Cloud requires the ``pyVmomi`` package, which is
available at PyPI:

https://pypi.python.org/pypi/pyvmomi

This package can be installed using `pip` or `easy_install`:

.. code-block:: bash

    pip install pyvmomi
    easy_install pyvmomi


Configuration
=============
The VMware cloud module needs the vCenter URL, username and password to be
set up in the cloud configuration at
``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      provider: vmware
      user: DOMAIN\user
      password: verybadpass
      url: vcenter01.domain.com

    vmware-vcenter02:
      provider: vmware
      user: DOMAIN\user
      password: verybadpass
      url: vcenter02.domain.com

    vmware-vcenter03:
      provider: vmware
      user: DOMAIN\user
      password: verybadpass
      url: vcenter03.domain.com


Profiles
========
Set up an initial profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/vmware.conf``:

.. code-block:: yaml

    vmware-centos6.5:
      provider: vmware-vcenter01
      clonefrom: test-vm

      ## Optional arguments
      num_cpus: 4
      memory: 8192
      disk:
        'Hard disk 2':
          size: 30
        'Hard disk 3':
          size: 20
        'Hard disk 4':
          size: 5
      network:
        'Network adapter 1':
          name: 10.20.30-400-Test
        'Network adapter 2':
          name: 10.30.40-500-Dev
          type: e1000
        'Network adapter 3':
          name: 10.40.50-600-Prod
          type: vmxnet3
      datastore: HUGE-DATASTORE-Cluster

      # If cloning from template, either resourcepool or cluster MUST be specified!
      resourcepool: Resources
      cluster: Prod

      folder: Development
      datacenter: DC1
      host: c4212n-002.domain.com
      template: False
      power_on: True


provider
    Enter the name that was specified when the cloud provider config was created.

clonefrom
    Enter the name of the VM/template to clone from.

num_cpus
    Enter the number of vCPUS you want the VM/template to have. If not specified, the current
    VM/template\'s vCPU count is used.

memory
    Enter memory (in MB) you want the VM/template to have. If not specified, the current
    VM/template\'s memory size is used.

disk
    Enter the disk specification here. If the hard disk doesn\'t exist, it will be created with
    the provided size. If the hard disk already exists, it will be expanded if the provided size
    is greater than the current size of the disk.

network
    Enter the network adapter specification here. If the network adapter doesn\'t exist, a new
    network adapter will be created with the specified network name and type. If the network
    adapter already exists, it will be reconfigured with the network name specified. Currently,
    only network adapters of type vmxnet, vmxnet2, vmxnet3, e1000 and e1000e can be created. If
    the network adapter type specified is not one of these, by default a network adapter of type
    vmxnet3 will be created.

datastore
    Enter the name of the datastore or the datastore cluster where the virtual machine should
    be located on physical storage. If not specified, the current datastore is used.

    .. note::

        - If you specify a datastore cluster name, DRS Storage recommendation is automatically
          applied.
        - If you specify a datastore name, DRS Storage recommendation is disabled.

resourcepool
    Enter the name of the resourcepool to which the new virtual machine should be
    attached. This determines what compute resources will be available to the clone.

    .. note::

        - For a clone operation from a virtual machine, it will use the same resourcepool as
          the original virtual machine unless specified.
        - For a clone operation from a template to a virtual machine, specifying either this
          or cluster is required. If both are specified, the resourcepool value will be used.
        - For a clone operation to a template, this argument is ignored.

cluster
    Enter the name of the cluster whose resource pool the new virtual machine should be
    attached to.

    .. note::

        - For a clone operation from a virtual machine, it will use the same cluster\'s
          resourcepool as the original virtual machine unless specified.
        - For a clone operation from a template to a virtual machine, specifying either
          this or resourcepool is required. If both are specified, the resourcepool value
          will be used.
        - For a clone operation to a template, this argument is ignored.

folder
    Enter the name of the folder that will contain the new virtual machine.

    .. note::

        - For a clone operation from a VM/template, the new VM/template will be added to the
          same folder that the original VM/template belongs to unless specified.
        - If both folder and datacenter are specified, the folder value will be used.

datacenter
    Enter the name of the datacenter that will contain the new virtual machine.

    .. note::

        - For a clone operation from a VM/template, the new VM/template will be added to the
          same folder that the original VM/template belongs to unless specified.
        - If both folder and datacenter are specified, the folder value will be used.

host
    Enter the name of the target host where the virtual machine should be registered.

    If not specified:

    .. note::

        - If resource pool is not specified, current host is used.
        - If resource pool is specified, and the target pool represents a stand-alone
          host, the host is used.
        - If resource pool is specified, and the target pool represents a DRS-enabled
          cluster, a host selected by DRS is used.
        - If resource pool is specified and the target pool represents a cluster without
          DRS enabled, an InvalidArgument exception be thrown.

template
    Specifies whether the new virtual machine should be marked as a template or not.
    Default is ``template: False``.

power_on
    Specifies whether the new virtual machine should be powered on or not. If ``template: True``
    is set, this field is ignored. Default is ``power_on: True``.
