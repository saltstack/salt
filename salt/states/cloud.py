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

import pprint
from salt._compat import string_types


def __virtual__():
    '''
    Only load if the cloud module is available in __salt__
    '''
    return 'cloud' if 'cloud.profile' in __salt__ else False


def _valid(name, comment='', changes=None):
    if not changes:
        changes = {}
    return {'name': name,
            'result': True,
            'changes': changes,
            'comment': comment}


def present(name, cloud_provider, onlyif=None, unless=None, **kwargs):
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

    cloud_provider
        The name of the cloud provider to use

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    instance = __salt__['cloud.action'](
        fun='show_instance', names=[name])
    retcode = __salt__['cmd.retcode']
    prov = str([a for a in instance][0])
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(name,
                                                                     prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.create'](cloud_provider, name, **kwargs)
    if info and not 'Error' in info:
        ret['changes'] = info
        ret['result'] = True
        ret['comment'] = ('Created instance {0} using provider {1}'
                          ' and the following options: {2}').format(
            name,
            cloud_provider,
            pprint.pformat(kwargs)
        )
    elif info and not 'Error' in info:
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
                          ' using profile {1},'
                          ' please check your configuration').format(name,
                                                                     profile)
        return ret


def absent(name, onlyif=None, unless=None):
    '''
    Ensure that no instances with the specified names exist.

    CAUTION: This is a destructive state, which will search all
    configured cloud providers for the named instance,
    and destroy it.

    name
        The name of the instance to destroy

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    retcode = __salt__['cmd.retcode']
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    if not instance:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be destroyed'.format(name)
        return ret
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
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


def profile(name, profile, onlyif=None, unless=None, **kwargs):
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

    onlyif
        Do run the state only if is unless succeed

    unless
        Do not run the state at least unless succeed

    kwargs
        Any profile override or addition

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    retcode = __salt__['cmd.retcode']
    if onlyif is not None:
        if not isinstance(onlyif, string_types):
            if not onlyif:
                return _valid(name, comment='onlyif execution failed')
        elif isinstance(onlyif, string_types):
            if retcode(onlyif) != 0:
                return _valid(name, comment='onlyif execution failed')
    if unless is not None:
        if not isinstance(unless, string_types):
            if unless:
                return _valid(name, comment='unless execution succeeded')
        elif isinstance(unless, string_types):
            if retcode(unless) == 0:
                return _valid(name, comment='unless execution succeeded')
    instance = __salt__['cloud.action'](fun='show_instance', names=[name])
    prov = str(instance.keys()[0])
    if instance and 'Not Actioned' not in prov:
        ret['result'] = True
        ret['comment'] = 'Instance {0} already exists in {1}'.format(
            name, prov)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Instance {0} needs to be created'.format(name)
        return ret
    info = __salt__['cloud.profile'](profile, name, vm_overrides=kwargs)
    if info and not 'Error' in info:
        node_info = info.get(name)
        ret['result'] = True
        default_msg = 'Created instance {0} using profile {1}'.format(
            name, profile,)
        # some providers support changes
        if 'changes' in node_info:
            ret['changes'] = node_info['changes']
            ret['comment'] = node_info.get('comment', default_msg)
        else:
            ret['changes'] = info
            ret['comment'] = default_msg
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
