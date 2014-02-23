# -*- coding: utf-8 -*-
'''
Using states instead of maps to deploy clouds
=============================================

.. versionadded:: 2014.1.0 (Hydrogen)

Use this minion to spin up a cloud instance:

.. code-block:: yaml

    my-ec2-instance:
      cloud.profile:
        my-ec2-config
'''

# Import python libs
import pprint

# Import salt libs
import salt._compat


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
    if isinstance(name, salt._compat.string_types):
        name = [minion_id.strip() for minion_id in name.split(',')]
    elif not isinstance(name, (list, tuple)):
        ret.setdefault('warnings', []).append(
            '\'name\' needs to be a string, a comma separated list of names '
            'or an actual list'
        )
        ret['result'] = False
        ret['comment'] = 'No VM(s) were destroyed'
        return ret

    # Make the variable plural to ease on code understanding
    names = name
    absent = set()
    destroy = set()
    failure = False
    for name in names:
        instance = __salt__['cloud.action'](fun='show_instance', names=[name])
        if not instance:
            absent.add(name)
            continue
        destroy.add(name)

    if __opts__['test']:
        ret['comment'] = ''
        if destroy:
            if len(destroy) > 1:
                ret['comment'] += 'Instances {0} need to be destroyed.'
            else:
                ret['comment'] += 'Instance {0} needs to be destroyed.'
            ret['comment'] = ret['comment'].format(', '.join(destroy))
        if absent:
            if len(absent) > 1:
                ret['comment'] += ' Instances {0} were already absent.'
            else:
                ret['comment'] += ' Instance {0} was already absent.'
            ret['comment'] = ret['comment'].format(', '.join(absent))
        return ret

    destroyed = set()
    failures = {}
    for name in destroy:
        info = __salt__['cloud.destroy'](name)
        if info and not 'Error' in info:
            ret['changes'][name] = info
            destroyed.add(name)
        elif 'Error' in info:
            failures[name] = info['Error']
        else:
            failures[name] = 'Failed to destroy instance {0}'.format(name)

    if failures:
        ret['result'] = False
        ret['failures'] = failures

    if destroyed:
        if ret['comment']:
            ret['comment'] += ' '
        if len(destroyed) > 1:
            ret['comment'] += 'Instances {0} were destroyed'
        else:
            ret['comment'] += 'Instance {0} was destroyed'
        ret['comment'] = ret['comment'].format(', '.join(destroyed))
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
