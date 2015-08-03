# -*- coding: utf-8 -*-
'''
Manage virt
===========

For the key certificate this state uses the external pillar in the master to call
for the generation and signing of certificates for systems running libvirt:

.. code-block:: yaml

    libvirt_keys:
      virt.keys
'''
from __future__ import absolute_import

# Import python libs
import os
import fnmatch

try:
    import libvirt  # pylint: disable=import-error
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


def __virtual__():
    '''
    Only if libvirt bindings for Python are installed.

    :return:
    '''

    return HAS_LIBVIRT


def keys(name, basepath='/etc/pki'):
    '''
    Manage libvirt keys.

    name
        The name variable used to track the execution

    basepath
        Defaults to ``/etc/pki``, this is the root location used for libvirt
        keys on the hypervisor
    '''
    #libvirt.serverkey.pem
    #libvirt.servercert.pem
    #libvirt.clientkey.pem
    #libvirt.clientcert.pem
    #libvirt.cacert.pem

    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    pillar = __salt__['pillar.ext']({'libvirt': '_'})
    paths = {
        'serverkey': os.path.join(basepath, 'libvirt', 'private', 'serverkey.pem'),
        'servercert': os.path.join(basepath, 'libvirt', 'servercert.pem'),
        'clientkey': os.path.join(basepath, 'libvirt', 'private', 'clientkey.pem'),
        'clientcert': os.path.join(basepath, 'libvirt', 'clientcert.pem'),
        'cacert': os.path.join(basepath, 'CA', 'cacert.pem')
    }

    for key in paths:
        p_key = 'libvirt.{0}.pem'.format(key)
        if p_key not in pillar:
            continue
        if not os.path.exists(os.path.dirname(paths[key])):
            os.makedirs(os.path.dirname(paths[key]))
        if os.path.isfile(paths[key]):
            with salt.utils.fopen(paths[key], 'r') as fp_:
                if fp_.read() != pillar[p_key]:
                    ret['changes'][key] = 'update'
        else:
            ret['changes'][key] = 'new'

    if not ret['changes']:
        ret['comment'] = 'All keys are correct'
    elif __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Libvirt keys are set to be updated'
        ret['changes'] = {}
    else:
        for key in ret['changes']:
            with salt.utils.fopen(paths[key], 'w+') as fp_:
                fp_.write(pillar['libvirt.{0}.pem'.format(key)])

        ret['comment'] = 'Updated libvirt certs and keys'

    return ret


def _virt_call(domain, function, section, comment, **kwargs):
    '''
    Helper to call the virt functions. Wildcards supported.

    :param domain:
    :param function:
    :param section:
    :param comment:
    :return:
    '''
    ret = {'name': domain, 'changes': {}, 'result': True, 'comment': ''}
    targeted_domains = fnmatch.filter(__salt__['virt.list_domains'](), domain)
    changed_domains = list()
    ignored_domains = list()
    for domain in targeted_domains:
        try:
            response = __salt__['virt.{0}'.format(function)](domain, **kwargs)
            if isinstance(response, dict):
                response = response['name']
            changed_domains.append({'domain': domain, function: response})
        except libvirt.libvirtError as err:
            ignored_domains.append({'domain': domain, 'issue': str(err)})
    if not changed_domains:
        ret['result'] = False
        ret['comment'] = 'No changes had happened'
        if ignored_domains:
            ret['changes'] = {'ignored': ignored_domains}
    else:
        ret['changes'] = {section: changed_domains}
        ret['comment'] = comment

    return ret


def rebooted(name):
    '''
    Reboots VMs

    .. versionadded:: Boron

    :param name:
    :return:
    '''

    return _virt_call(name, 'reboot', 'rebooted', "Machine has been rebooted")


def stopped(name):
    '''
    Stops a VM by shutting it down nicely.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'shutdown', 'stopped', "Machine has been shut down")


def unpowered(name):
    '''
    Stops a VM by power off.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'stop', 'unpowered', 'Machine has been powered off')


def running(name):
    '''
    Starts a VM.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.running
    '''

    return _virt_call(name, 'start', 'running', 'Machine has been started')


def saved(name, suffix=None):
    '''
    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.saved:
            - suffix: periodic

        domain*:
          virt.saved:
            - suffix: periodic
    '''

    return _virt_call(name, 'snapshot', 'saved', 'Snapshots has been taken', suffix=suffix)


def reverted(name, snapshot=None, cleanup=False):
    '''
    Reverts to the particular snapshot.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.reverted:
            - cleanup: True

        domain_name_1:
          virt.reverted:
            - snapshot: snapshot_name
            - cleanup: False
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    try:
        domains = fnmatch.filter(__salt__['virt.list_domains'](), name)
        if not domains:
            ret['comment'] = 'No domains found for criteria "{0}"'.format(name)
        else:
            ignored_domains = list()
            if len(domains) > 1:
                ret['changes'] = {'reverted': list()}
            for domain in domains:
                result = {}
                try:
                    result = __salt__['virt.revert_snapshot'](domain, snapshot=snapshot, cleanup=cleanup)
                    result = {'domain': domain, 'current': result['reverted'], 'deleted': result['deleted']}
                except CommandExecutionError as err:
                    if len(domains) > 1:
                        ignored_domains.append({'domain': domain, 'issue': str(err)})
                if len(domains) > 1:
                    if result:
                        ret['changes']['reverted'].append(result)
                else:
                    ret['changes'] = result
                    break

            ret['result'] = len(domains) != len(ignored_domains)
            if ret['result']:
                ret['comment'] = 'Domain{0} has been reverted'.format(len(domains) > 1 and "s" or "")
            if ignored_domains:
                ret['changes']['ignored'] = ignored_domains
            if not ret['changes']['reverted']:
                ret['changes'].pop('reverted')
    except libvirt.libvirtError as err:
        ret['comment'] = str(err)
    except CommandExecutionError as err:
        ret['comment'] = str(err)

    return ret
