# -*- coding: utf-8 -*-
'''
Manage libvirt certificates
===========================

This state uses the external pillar in the master to call
for the generation and signing of certificates for systems running libvirt:

.. code-block:: yaml

    libvirt_keys:
      libvirt.keys
'''
from __future__ import absolute_import

# Import python libs
import os

# Import salt libs
import salt.utils


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

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    pillar = __salt__['pillar.ext']({'libvirt': '_'})
    paths = {
            'serverkey': os.path.join(
                basepath,
                'libvirt',
                'private',
                'serverkey.pem'),
            'servercert': os.path.join(
                basepath,
                'libvirt',
                'servercert.pem'),
            'clientkey': os.path.join(
                basepath,
                'libvirt',
                'private',
                'clientkey.pem'),
            'clientcert': os.path.join(
                basepath,
                'libvirt',
                'clientcert.pem'),
            'cacert': os.path.join(
                basepath,
                'CA',
                'cacert.pem')}
    for key in paths:
        p_key = 'libvirt.{0}.pem'.format(key)
        if p_key not in pillar:
            continue
        if not os.path.isdir(os.path.dirname(paths[key])):
            os.makedirs(os.path.dirname(paths[key]))
        if os.path.isfile(paths[key]):
            with salt.utils.fopen(paths[key], 'r') as fp_:
                if fp_.read() != pillar[p_key]:
                    ret['changes'][key] = 'update'
        else:
            ret['changes'][key] = 'new'
    if not ret['changes']:
        ret['comment'] = 'All keys are correct'
        return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Libvirt keys are set to be updated'
        ret['changes'] = {}
        return ret
    for key in ret['changes']:
        with salt.utils.fopen(paths[key], 'w+') as fp_:
            fp_.write(pillar['libvirt.{0}.pem'.format(key)])
    ret['comment'] = 'Updated libvirt certs and keys'
    return ret
