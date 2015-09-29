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

__virtualname__ = 'virt'


def __virtual__():
    '''
    Only if virt module is available.

    :return:
    '''

    if 'virt.node_info' in __salt__:
        return __virtualname__
    return False


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


def stopped(name):
    '''
    Stops a VM by shutting it down nicely.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''

    return _virt_call(name, 'shutdown', 'stopped', "Machine has been shut down")


def running(name, **kwargs):
    '''
    Starts an existing guest, or defines and starts a new VM with specified arguments.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.running

    .. code-block:: yaml

        domain_name:
          virt.running:
            - cpu: 2
            - mem: 2048
            - eth0_mac: 00:00:6a:53:00:e3

    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': '{0} is running'.format(name)
           }

    kwargs = salt.utils.clean_kwargs(**kwargs)
    cpu = kwargs.pop('cpu', False)
    mem = kwargs.pop('mem', False)
    image = kwargs.pop('image', False)

    try:
        try:
            __salt__['virt.vm_state'](name)
            if __salt__['virt.vm_state'](name) != 'running':
                __salt__['virt.start'](name)
                ret['changes'][name] = 'Domain started'
                ret['comment'] = 'Domain {0} started'.format(name)
        except CommandExecutionError:
            kwargs = salt.utils.clean_kwargs(**kwargs)
            __salt__['virt.init'](name, cpu=cpu, mem=mem, image=image, **kwargs)
            ret['changes'][name] = 'Domain defined and started'
            ret['comment'] = 'Domain {0} defined and started'.format(name)
    except libvirt.libvirtError:
        ret['comment'] = 'Domain {0} exists and is running'.format(name)

    return ret


def snapshot(name, suffix=None):
    '''
    Takes a snapshot of a particular VM or by a UNIX-style wildcard.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.snapshot:
            - suffix: periodic

        domain*:
          virt.snapshot:
            - suffix: periodic
    '''

    return _virt_call(name, 'snapshot', 'saved', 'Snapshot has been taken', suffix=suffix)