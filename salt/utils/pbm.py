# -*- coding: utf-8 -*-
'''
Library for VMware Storage Policy management (via the pbm endpoint)

This library is used to manage the various policies available in VMware

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
'''

# Import Python Libs
from __future__ import absolute_import
import logging

# Import Salt Libs
import salt.utils.vmware
from salt.exceptions import VMwareApiError, VMwareRuntimeError, \
        VMwareObjectRetrievalError


try:
    from pyVmomi import pbm, vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if PyVmomi is installed.
    '''
    if HAS_PYVMOMI:
        return True
    else:
        return False, 'Missing dependency: The salt.utils.pbm module ' \
                'requires the pyvmomi library'


def get_profile_manager(service_instance):
    '''
    Returns a profile manager

    service_instance
        Service instance to the host or vCenter
    '''
    stub = salt.utils.vmware.get_new_service_instance_stub(
        service_instance, ns='pbm/2.0', path='/pbm/sdk')
    pbm_si = pbm.ServiceInstance('ServiceInstance', stub)
    try:
        profile_manager = pbm_si.RetrieveContent().profileManager
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    return profile_manager


def get_placement_solver(service_instance):
    '''
    Returns a placement solver

    service_instance
        Service instance to the host or vCenter
    '''
    stub = salt.utils.vmware.get_new_service_instance_stub(
        service_instance, ns='pbm/2.0', path='/pbm/sdk')
    pbm_si = pbm.ServiceInstance('ServiceInstance', stub)
    try:
        profile_manager = pbm_si.RetrieveContent().placementSolver
    except vim.fault.NoPermission as exc:
        log.exception(exc)
        raise VMwareApiError('Not enough permissions. Required privilege: '
                             '{0}'.format(exc.privilegeId))
    except vim.fault.VimFault as exc:
        log.exception(exc)
        raise VMwareApiError(exc.msg)
    except vmodl.RuntimeFault as exc:
        log.exception(exc)
        raise VMwareRuntimeError(exc.msg)
    return profile_manager
