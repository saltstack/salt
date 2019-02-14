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
    Ensure that the named snap package is installed

    name
        The snap package

    channel
        Optional. The channel to install the package from.
    '''
    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': None,
           'comment': ''}

    old = __salt__['snap.versions_installed'](name)
    if not old:
        if __opts__['test']:
            ret['comment'] = 'Package "{0}" would have been installed'.format(name)
            ret['pchanges']['new'] = name
            ret['pchanges']['old'] = None
            ret['result'] = None
            return ret

        install = __salt__['snap.install'](name, channel=channel)
        if install['result']:
            ret['comment'] = 'Package "{0}" was installed'.format(name)
            ret['changes']['new'] = name
            ret['changes']['old'] = None
            ret['result'] = True
            return ret

        ret['comment'] = 'Package "{0}" failed to install'.format(name)
        ret['comment'] += '\noutput:\n' + install['output']
        ret['result'] = False
        return ret

    # Currently snap always returns only one line?
    old_channel = old[0]['tracking']
    if old_channel != channel and channel is not None:
        if __opts__['test']:
            ret['comment'] = 'Package "{0}" would have been switched to channel {1}'.format(name, channel)
            ret['pchanges']['old_channel'] = old_channel
            ret['pchanges']['new_channel'] = channel
            ret['result'] = None
            return ret

        refresh = __salt__['snap.install'](name, channel=channel, refresh=True)
        if refresh['result']:
            ret['comment'] = 'Package "{0}" was switched to channel {1}'.format(name, channel)
            ret['pchanges']['old_channel'] = old_channel
            ret['pchanges']['new_channel'] = channel
            ret['result'] = True
            return ret

        ret['comment'] = 'Failed to switch Package "{0}" to channel {1}'.format(name, channel)
        ret['comment'] += '\noutput:\n' + install['output']
        ret['result'] = False
        return ret

    ret['comment'] = 'Package "{0}" is already installed'.format(name)
    if __opts__['test']:
        ret['result'] = None
        return ret

    ret['result'] = True
    return ret


def removed(name):
    '''
    Ensure that the named snap package is not installed

    name
        The snap package
    '''

    ret = {'name': name,
           'changes': {},
           'pchanges': {},
           'result': None,
           'comment': ''}

    old = __salt__['snap.versions_installed'](name)
    if not old:
        ret['comment'] = 'Package {0} is not installed'.format(name)
        ret['result'] = True
        return ret

    if __opts__['test']:
        ret['comment'] = 'Package {0} would have been removed'.format(name)
        ret['result'] = None
        ret['pchanges']['old'] = old[0]['version']
        ret['pchanges']['new'] = None
        return ret

    remove = __salt__['snap.remove'](name)
    ret['comment'] = 'Package {0} removed'.format(name)
    ret['result'] = True
    ret['changes']['old'] = old[0]['version']
    ret['changes']['new'] = None
    return ret
