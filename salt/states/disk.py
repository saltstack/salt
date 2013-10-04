# -*- coding: utf-8 -*-
'''
Disk monitoring state

Monitor the state of disk resources
'''

__monitor__ = [
        'status',
        ]


def status(name, max=None, min=None):
    '''
    Return the current disk usage stats for the named device
    '''
    # Monitoring state, no changes will be made so no test interface needed
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {},
           'data': {}}  # Data field for monitoring state

    data = __salt__['disk.usage']()
    if name not in data:
        ret['result'] = False
        ret['comment'] += 'Named disk mount not present '
        return ret
    if max:
        try:
            if isinstance(max, basestring):
                max = int(max.strip('%'))
        except Exception:
            ret['comment'] += 'Max argument must be an integer '
    if min:
        try:
            if isinstance(min, basestring):
                min = int(min.strip('%'))
        except Exception:
            ret['comment'] += 'Min argument must be an integer '
    if min and max:
        if min >= max:
            ret['comment'] += 'Min must be less than max'
    if ret['comment']:
        return ret
    cap = int(data[name]['capacity'].strip('%'))
    ret['data'] = data[name]
    if min:
        if cap < min:
            ret['comment'] = 'Disk is below minimum of {0} at {1}'.format(
                    min, cap)
            return ret
    if max:
        if cap > max:
            ret['comment'] = 'Disk is below maximum of {0} at {1}'.format(
                    max, cap)
            return ret
    ret['comment'] = 'Disk in acceptable range'
    ret['result'] = True
    return ret
