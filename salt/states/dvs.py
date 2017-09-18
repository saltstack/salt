# -*- coding: utf-8 -*-
'''
Manage VMware distributed virtual switches (DVSs).

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

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import traceback

# Import Salt Libs
import salt.exceptions
from salt.utils.dictupdate import update as dict_merge
import salt.utils

# Get Logging Started
log = logging.getLogger(__name__)

def __virtual__():
    return True


def mod_init(low):
    '''
    Init function
    '''
    return True
