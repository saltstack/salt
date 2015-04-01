===================================
Getting Started With VMware vSphere
===================================

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
      datastore: na-001-004
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
    VM/template's vCPU count is used.

memory
    Enter memory (in MB) you want the VM/template to have. If not specified, the current
    VM/template's memory size is used.

datastore
    Enter the name of the datastore or the datastore cluster where the virtual machine should
    be located on physical storage. If not specified, the current datastore is used.
    - If you specify a datastore cluster name, DRS Storage recommendation is automatically
      applied.
    - If you specify a datastore name, DRS Storage recommendations is disabled.

resourcepool
    Enter the name of the resourcepool to which the new virtual machine should be
    attached. This determines what compute resources will be available to the clone. 
    - For a clone operation from a virtual machine, it will use the same resourcepool as
      the original virtual machine unless specified.
    - For a clone operation from a template to a virtual machine, specifying either this
      or cluster is required. If both are specified, the resourcepool value will be used.
    - For a clone operation to a template, this argument is ignored.

cluster
    Enter the name of the cluster whose resource pool the new virtual machine should be
    attached to. 
    - For a clone operation from a virtual machine, it will use the same clusters resourcepool
      as the original virtual machine unless specified.
    - For a clone operation from a template to a virtual machine, specifying either this
      or resourcepool is required. If both are specified, the resourcepool value will be used.
    - For a clone operation to a template, this argument is ignored.

folder
    Enter the name of the folder that will contain the new virtual machine.
    - For a clone operation from a virtual machine, the new VM will be added to the same folder
      that the original VM belongs to unless specified.
    - For a clone operation from a template to a virtual machine, specifying either this
      or datacenter is required. If both are specified, the folder value will be used.

datacenter
    Enter the name of the datacenter that will contain the new virtual machine.
    - For a clone operation from a virtual machine, the new VM will be added to the same folder
      that the original VM belongs to unless specified.
    - For a clone operation from a template to a virtual machine, specifying either this
      or folder is required. If both are specified, the folder value will be used.

host
    Enter the name of the target host where the virtual machine should be registered. 
    If not specified:

    .. code-block:: text

        - if resource pool is not specified, current host is used.
        - if resource pool is specified, and the target pool represents a stand-alone
          host, the host is used.
        - if resource pool is specified, and the target pool represents a DRS-enabled
          cluster, a host selected by DRS is used.
        - if resource pool is specified and the target pool represents a cluster without
          DRS enabled, an InvalidArgument exception be thrown.

template
    Specifies whether the new virtual machine should be marked as a template or not.
    Default is ``False``.

power_on
    Specifies whether the new virtual machine should be powered on or not. Default is
    ``True``.
