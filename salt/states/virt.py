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
try:
    import libvirt  # pylint: disable=import-error
    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False

# Import salt libs
import salt.utils


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
        'clientcert': os.path.join(basepath,'libvirt','clientcert.pem'),
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


def stopped(name):
    '''
    Stops a VM

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.stopped
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        ret['result'] = __salt__['virt.stop'](name)
    except libvirt.libvirtError as err:
        ret['result'] = False
        ret['comment'] = str(err)

    if ret['result']:
        ret['changes'] = {'stopped': name}
        ret['comment'] = "Machine has been abruptly turned off"

    return ret


def running(name):
    '''
    Starts a VM.

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.running
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    try:
        ret['result'] = __salt__['virt.start'](name)
    except libvirt.libvirtError as err:
        ret['result'] = False
        ret['comment'] = str(err)

    if ret['result']:
        ret['changes'] = {'running': name}
        ret['comment'] = "Machine has been started"

    return ret


def saved(name, suffix=None):
    '''
    Takes a snapshot of a particular VM.

    :param name:

    .. versionadded:: Boron

    .. code-block:: yaml

        domain_name:
          virt.saved:
            - suffix: periodic
    '''
    ret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}

    snapshot_name = None
    try:
        snapshot_name = __salt__['virt.snapshot'](name, name=None, suffix=suffix)['name']
        ret['result'] = True
    except libvirt.libvirtError as err:
        ret['result'] = False
        ret['comment'] = str(err)

    if ret['result'] and snapshot_name:
        ret['changes'] = {'domain': name}
        ret['comment'] = 'Snapshot "{0}" has been taken'.format(snapshot_name)

    return ret

