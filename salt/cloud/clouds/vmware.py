# -*- coding: utf-8 -*-
'''
VMware Cloud Module
===================

.. versionadded:: Beryllium

The VMware cloud module allows you to manage VMware ESX, ESXi, and vCenter.

:depends:   - pyVmomi Python module

Note: Ensure python pyVmomi module is installed by running following one-liner
check. The output should be 0.

.. code-block:: bash

   python -c "import pyVmomi" ; echo $?

Use of this module requires a vCenter Host URL, username and password to set
up authentication. Set up the cloud configuration at:

``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/vmware.conf``:

.. code-block:: yaml

    my-vmware-config:
      provider: vmware
      user: myuser
      password: verybadpass
      host: 'vcenter01.domain.com'
'''
