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
import logging
import ssl

# Import Salt Libs
from salt.exceptions import VMwareApiError, VMwareRuntimeError
import salt.utils.vmware

try:
    from pyVmomi import vim, vmodl
    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False


try:
    from salt.ext.vsan import vsanapiutils
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


def vsan_supported(service_instance):
    '''
    Returns whether vsan is supported on the vCenter:
        api version needs to be 6 or higher

    service_instance
        Service instance to the host or vCenter
    '''
    try:
        api_version = service_instance.content.about.apiVersion
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
    if int(api_version.split('.')[0]) < 6:
        return False
    return True


def get_vsan_cluster_config_system(service_instance):
    '''
    Returns a vim.cluster.VsanVcClusterConfigSystem object

    service_instance
        Service instance to the host or vCenter
    '''

    #TODO Replace when better connection mechanism is available

    #For python 2.7.9 and later, the defaul SSL conext has more strict
    #connection handshaking rule. We may need turn of the hostname checking
    #and client side cert verification
    context = None
    if sys.version_info[:3] > (2, 7, 8):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    stub = service_instance._stub
    vc_mos = vsanapiutils.GetVsanVcMos(stub, context=context)
    return vc_mos['vsan-cluster-config-system']


def get_cluster_vsan_info(cluster_ref):
    '''
    Returns the extended cluster vsan configuration object
    (vim.VsanConfigInfoEx).

    cluster_ref
        Reference to the cluster
    '''

    cluster_name = salt.utils.vmware.get_managed_object_name(cluster_ref)
    log.trace('Retrieving cluster vsan info of cluster '
              '\'{0}\''.format(cluster_name))
    si = salt.utils.vmware.get_service_instance_from_managed_object(
        cluster_ref)
    vsan_cl_conf_sys = get_vsan_cluster_config_system(si)
    try:
        return vsan_cl_conf_sys.VsanClusterGetConfig(cluster_ref)
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
