# -*- coding: utf-8 -*-
'''
States to manage OpenStack Nova
===============================

.. versionadded:: Helium

Use this minion to do things with nova:

.. code-block:: yaml

    myblock:
      nova.volume_exists:
        - size: 100
'''

# Import salt cloud utils for check
import salt.utils.cloud as suc


def __virtual__():
    '''
    Only load if the nova module is available in __salt__
    '''
    return 'nova' if 'nova.server_list' in __salt__ else False


def _check_name(name):
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if suc.check_name(name, 'a-zA-Z0-9._-'):
        ret['comment'] = 'Invalid characters in name.'
        ret['result'] = False
        return ret
    else:
        ret['result'] = True
        return ret


def volume_exists(name, profile=None, **kwargs):
    '''
    Check that a block volume exists.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    volume = __salt__['nova.volume_show'](name=name, profile=profile)

    if volume:
        ret['comment'] = 'Volume exists: {0}'.format(name)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be created.'.format(name)
        ret['result'] = None
        return ret

    response = __salt__['nova.volume_create'](
        name=name,
        profile=profile,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was created'.format(name)
        ret['changes'] = {'old': None, 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to create.'.format(name)
    return ret


def volume_attached(name, server_name, profile=None, **kwargs):
    '''
    Check if a block volume is attached.
    '''
    ret = _check_name(name)
    if not ret['result']:
        return ret

    ret = _check_name(server_name)
    if not ret['result']:
        return ret

    volume = __salt__['nova.volume_show'](
        name=name,
        profile=profile
    )
    server = __salt__['nova.server_by_name'](server_name, profile=profile)

    if volume and volume['attachments']:
        ret['comment'] = ('Volume {name} is already'
                          'attached: {attachments}').format(**volume)
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'Volume {0} will be will be attached.'.format(
            name
        )
        ret['result'] = None
        return ret
    elif not volume:
        ret['comment'] = 'Volume {0} does not exist'.format(name)
        ret['result'] = False
        return ret
    elif not server:
        ret['comment'] = 'Server {0} does not exist'.format(server_name)
        ret['result'] = False
        return ret

    response = __salt__['nova.volume_attach'](
        name,
        server_name,
        profile=profile,
        **kwargs
    )
    if response:
        ret['result'] = True
        ret['comment'] = 'Volume {0} was created'.format(name)
        ret['changes'] = {'old': volume, 'new': response}
    else:
        ret['result'] = False
        ret['comment'] = 'Volume {0} failed to attach.'.format(name)
    return ret
