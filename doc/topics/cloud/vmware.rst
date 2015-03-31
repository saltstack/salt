===================================
Getting Started With VMware vSphere
===================================

VMware vSphere is a server virtualization platform for building cloud
infrastructure.


Dependencies
============
The ``vmware`` module for Salt Cloud requires the ``pyVmomi`` package, which is
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
``/etc/salt/cloud.profiles.d/vmware.conf``

Example:

.. code-block:: yaml

    vmware-centos6.5:
      provider: vmware-vcenter01
      clonefrom: test-vm
      ## Optional arguments
      datastore: datastorename
      resourcepool: resourcepool
      folder: Development
      host: c4212n-002.domain.com
      template: False
      power_on: True


provider
~~~~~~~~
Enter the name that was specified when the cloud provider config was created.

clonefrom
~~~~~~~~~
Enter the name of the VM/template to clone from. 

datastore
~~~~~~~~~
Enter the name of the datastore where the virtual machine should be located. If
not specified, the current datastore is used.

resourcepool
~~~~~~~~~~~~
Enter the name of the resourcepool to which the new virtual machine should be
attached. If not specified, it will use the same resourcepool as the original vm.
For a clone operation to a template, this argument is ignored. For a clone operation
from a template to a virtual machine, this argument is required.

folder
~~~~~~
Enter the name of the folder that will contain the new virtual machine. If not
specified, the new VM will be added to the folder that the original VM belongs to.

host
~~~~
Enter the name of the target host where the virtual machine should be registered. 
If not specified:

  * if resource pool is not specified, current host is used.
  * if resource pool is specified, and the target pool represents a stand-alone
    host, the host is used.
  * if resource pool is specified, and the target pool represents a DRS-enabled
    cluster, a host selected by DRS is used.
  * if resource pool is specified and the target pool represents a cluster without
    DRS enabled, an InvalidArgument exception be thrown.

template
~~~~~~~~
Specifies whether the new virtual machine should be marked as a template or not.
Default is ``False``.

power_on
~~~~~~~~
Specifies whether the new virtual machine should be powered on or not. Default is
``True``.
