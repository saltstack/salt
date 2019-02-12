# -*- coding: utf-8 -*-
'''
Management of snap packages
===============================================
'''
from __future__ import absolute_import, print_function, unicode_literals
import salt.utils.path

__virtualname__ = 'snap'


def __virtual__():
    if salt.utils.path.which('snap'):
        return __virtualname__

    return (False, 'The snap state module cannot be loaded: the "snap" binary is not in the path.')


def installed(name, channel=None):
    '''
    Ensure that the snap package is installed

    name : str
        The snap package

    channel : str
        Optional. The channel to install the package from.
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    old = __salt__['snap.versions_installed'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Package "{0}" would have been installed'.format(name)
            ret['pchanges']['installed'] = name
            ret['result'] = None
            return ret

        if __salt__['snap.install'](name, channel):
            ret['comment'] = 'Package "{0}" was installed'.format(name)
            ret['changes']['installed'] = name
            ret['result'] = True
            return ret
