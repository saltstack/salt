# -*- coding: utf-8 -*-
'''
Manages VMware storage policies
(called pbm because the vCenter endpoint is /pbm)

Examples
========

Storage policy
--------------

.. code-block:: python

{
    "name": "salt_storage_policy"
    "description": "Managed by Salt. Random capability values.",
    "resource_type": "STORAGE",
    "subprofiles": [
        {
            "capabilities": [
                {
                    "setting": {
                        "type": "scalar",
                        "value": 2
                    },
                    "namespace": "VSAN",
                    "id": "hostFailuresToTolerate"
                },
                {
                    "setting": {
                        "type": "scalar",
                        "value": 2
                    },
                    "namespace": "VSAN",
                    "id": "stripeWidth"
                },
                {
                    "setting": {
                        "type": "scalar",
                        "value": true
                    },
                    "namespace": "VSAN",
                    "id": "forceProvisioning"
                },
                {
                    "setting": {
                        "type": "scalar",
                        "value": 50
                    },
                    "namespace": "VSAN",
                    "id": "proportionalCapacity"
                },
                {
                    "setting": {
                        "type": "scalar",
                        "value": 0
                    },
                    "namespace": "VSAN",
                    "id": "cacheReservation"
                }
            ],
            "name": "Rule-Set 1: VSAN",
            "force_provision": null
        }
    ],
}

Dependencies
============


- pyVmomi Python Module


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537
'''

# Import Python Libs
from __future__ import absolute_import
import sys
import logging
import json
import time
import copy

# Import Salt Libs
from salt.exceptions import CommandExecutionError, ArgumentValueError
import salt.modules.vsphere as vsphere
from salt.utils import is_proxy
from salt.utils.dictdiffer import recursive_diff
from salt.utils.listdiffer import list_diff

# External libraries
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Get Logging Started
log = logging.getLogger(__name__)
# TODO change with vcenter
ALLOWED_PROXY_TYPES = ['esxcluster', 'vcenter']
LOGIN_DETAILS = {}

def __virtual__():
    if HAS_JSONSCHEMA:
        return True
    return False


def mod_init(low):
    '''
    Init function
    '''
    return True
