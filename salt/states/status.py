# -*- coding: utf-8 -*-
'''
Minion status monitoring

Maps to the `status` execution module.
'''

__monitor__ = [
        'loadavg',
        ]


def loadavg(name, maximum=None, minimum=None):
    '''
    Return the current load average for the specified minion. Available values
    for name are `1-min`, `5-min` and `15-min`. `minimum` and `maximum` values
    should be passed in as strings.
    '''
    # Monitoring state, no changes will be made so no test interface needed
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {},
           'data': {}}  # Data field for monitoring state

    data = __salt__['status.loadavg']()
    if name not in data:
        ret['result'] = False
        ret['comment'] += 'Requested load average {0} not available '.format(
            name
        )
        return ret
    if minimum and maximum and minimum >= maximum:
        ret['comment'] += 'Min must be less than max'
    if ret['comment']:
        return ret
    cap = float(data[name])
    ret['data'] = data[name]
    if minimum:
        if cap < float(minimum):
            ret['comment'] = 'Load avg is below minimum of {0} at {1}'.format(
                    minimum, cap)
            return ret
    if maximum:
        if cap > float(maximum):
            ret['comment'] = 'Load avg above maximum of {0} at {1}'.format(
                    maximum, cap)
            return ret
    ret['comment'] = 'Load avg in acceptable range'
    ret['result'] = True
    return ret
