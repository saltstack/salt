# -*- coding: utf-8 -*-
'''
Connection library for VMware vSAN endpoint

This library used the vSAN extension of the VMware SDK
used to manage vSAN related objects

:codeauthor: Alexandru Bleotu <alexandru.bleotu@morganstaley.com>

Dependencies
~~~~~~~~~~~~

- pyVmomi Python Module

pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original VMware utils file
was developed against.
'''

# Import Python Libs
from __future__ import absolute_import
import sys
import atexit
import logging
import time
import re
import ssl

# Import Salt Libs
from salt.exceptions import VMwareApiError, VMwareRuntimeError
import salt.utils.vmware

try:
    from pyVmomi import VmomiSupport, SoapStubAdapter, vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


try:
    from salt.ext.vsan import vsanmgmtObjects, vsanapiutils
    HAS_PYVSAN = True
except ImportError:
    HAS_PYVSAN = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if PyVmomi is installed.
    '''
    if HAS_PYVSAN and HAS_PYVMOMI:
        return True
    else:
        return False, 'Missing dependency: The salt.utils.vsan module ' \
                'requires pyvmomi and the pyvsan extension library'
