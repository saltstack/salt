# -*- coding: utf-8 -*-
'''
Using states instead of maps to deploy clouds
=============================================

.. versionadded:: Hydrogen

Use this minion to spin up a cloud instance:

.. code-block:: yaml

    my-ec2-instance:
      cloud.profile:
        my-ec2-config
'''

import pprint


def __virtual__():
    '''
    Only load if the cloud module is available in __salt__
    '''
    return 'cloud' if 'cloud.profile' in __salt__ else False


def present(name, provider, **kwargs):
    '''
    Spin up a single instance on a cloud provider, using salt-cloud. This state
    does not take a profile argument; rather, it takes the arguments that would
    normally be configured as part of the state.

    Note that while this function does take any configuration argument that
    would normally be used to create an instance, it will not verify the state
    of any of those arguments on an existing instance. Stateful properties of
    an instance should be configured using their own individual state (i.e.,
    cloud.tagged, cloud.untagged, etc).

    name
        The name of the instance to create

    provider
        The name of the cloud provider to use
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    prov = str(instance.keys()[0])
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(name, prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.create'](provider, name, **kwargs)
    if info and not 'Error' in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = ('Created instance {0} using provider {1}'
                          'and the following options: {2}').format(
            name,
            provider,
            pprint.pformat(kwargs)
        )
    elif 'Error' in info:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}: {2}').format(
            name,
            profile,
            info['Error'],
        )
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}').format(
            name,
            profile,
        )
    return ret


def absent(name):
    '''
    Ensure that no instances with the specified names exist.

    CAUTION: This is a destructive state, which will search all configured cloud
    providers for the named instance, and destroy it.

    name
        The name of the instance to destroy
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    if not instance:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be destroyed'.format(name)
        return ret
    info = __salt__['cloud.destroy'](name)
    if info and not 'Error' in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = ('Destroyed instance {0}').format(
            name,
        )
    elif 'Error' in info:
        ret['result'] = False
        ret['comment'] = ('Failed to destroy instance {0}: {1}').format(
            name,
            info['Error'],
        )
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to destroy instance {0}'.format(name)
    return ret


def profile(name, profile):
    '''
    Create a single instance on a cloud provider, using a salt-cloud profile.

    Note that while profiles used this function do take any configuration
    argument that would normally be used to create an instance using a profile,
    this state will not verify the state of any of those arguments on an
    existing instance. Stateful properties of an instance should be configured
    using their own individual state (i.e., cloud.tagged, cloud.untagged, etc).

    name
        The name of the instance to create

    profile
        The name of the cloud profile to use
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    prov = str(instance.keys()[0])
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(name, prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.profile'](profile, name)
    if info and not 'Error' in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = 'Created instance {0} using profile {1}'.format(
            name,
            profile,
        )
    elif 'Error' in info:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}: {2}').format(
            name,
            profile,
            info['Error'],
        )
    else:
        ret['result'] = False
        ret['comment'] = ('Failed to create instance {0}'
                          'using profile {1}').format(
            name,
            profile,
        )
    return ret
