# -*- coding: utf-8 -*-
'''
Management of the Salt beacons
==============================

.. versionadded:: 2015.8.0

.. code-block:: yaml

    ps:
      beacon.present:
        - enable: False
        - salt-master: running
        - apache2: stopped

    sh:
      beacon.present:

    load:
      beacon.present:
        - 1m:
            - 0.0
            - 2.0
        - 5m:
            - 0.0
            - 1.5
        - 15m:
            - 0.1
            - 1.0

'''
from __future__ import absolute_import
import logging
log = logging.getLogger(__name__)


def present(name,
            **kwargs):
    '''
    Ensure beacon is configured with the included beacon data.

    name
        The name of the beacon ensure is configured.

    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_beacons = __salt__['beacons.list'](return_yaml=False)
    beacon_data = kwargs

    if name in current_beacons:

        if beacon_data == current_beacons[name]:
            ret['comment'].append('Job {0} in correct state'.format(name))
        else:
            if 'test' in __opts__ and __opts__['test']:
                kwargs['test'] = True
                result = __salt__['beacons.modify'](name, beacon_data, **kwargs)
                ret['comment'].append(result['comment'])
                ret['changes'] = result['changes']
            else:
                result = __salt__['beacons.modify'](name, beacon_data, **kwargs)
                if not result['result']:
                    ret['result'] = result['result']
                    ret['comment'] = result['comment']
                    return ret
                else:
                    if 'changes' in result:
                        ret['comment'].append('Modifying {0} in beacons'.format(name))
                        ret['changes'] = result['changes']
                    else:
                        ret['comment'].append(result['comment'])
    else:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['beacons.add'](name, beacon_data, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['beacons.add'](name, beacon_data, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Adding {0} to beacons'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def absent(name, **kwargs):
    '''
    Ensure beacon is absent.

    name
        The name of the beacon ensured absent.

    '''
    ### NOTE: The keyword arguments in **kwargs are ignored in this state, but
    ###       cannot be removed from the function definition, otherwise the use
    ###       of unsupported arguments will result in a traceback.

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_beacons = __salt__['beacons.list'](return_yaml=False)
    if name in current_beacons:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['beacons.delete'](name, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['beacons.delete'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Removed {0} from beacons'.format(name))
    else:
        ret['comment'].append('{0} not configured in beacons'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def enabled(name, **kwargs):
    '''
    Enable a beacon.

    name
        The name of the beacon to enable.

    '''
    ### NOTE: The keyword arguments in **kwargs are ignored in this state, but
    ###       cannot be removed from the function definition, otherwise the use
    ###       of unsupported arguments will result in a traceback.

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_beacons = __salt__['beacons.list'](show_all=True, return_yaml=False)
    if name in current_beacons:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['beacons.enable_beacon'](name, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['beacons.enable_job'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Enabled {0} from beacons'.format(name))
    else:
        ret['comment'].append('{0} not a configured beacon'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret


def disabled(name, **kwargs):
    '''
    Disable a beacon.

    name
        The name of the beacon to enable.

    '''
    ### NOTE: The keyword arguments in **kwargs are ignored in this state, but
    ###       cannot be removed from the function definition, otherwise the use
    ###       of unsupported arguments will result in a traceback.

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    current_beacons = __salt__['beacons.list'](show_all=True, return_yaml=False)
    if name in current_beacons:
        if 'test' in __opts__ and __opts__['test']:
            kwargs['test'] = True
            result = __salt__['beacons.disable_beacon'](name, **kwargs)
            ret['comment'].append(result['comment'])
        else:
            result = __salt__['beacons.disable_beacon'](name, **kwargs)
            if not result['result']:
                ret['result'] = result['result']
                ret['comment'] = result['comment']
                return ret
            else:
                ret['comment'].append('Disabled beacon {0}.'.format(name))
    else:
        ret['comment'].append('Job {0} is not configured.'.format(name))

    ret['comment'] = '\n'.join(ret['comment'])
    return ret
