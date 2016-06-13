# -*- coding: utf-8 -*-
'''
Disk monitoring state

Monitor the state of disk resources.

The ``disk.status`` function can be used to report that the used space of a
filesystem is within the specified limits.

.. code-block:: sls

    used_space:
      disk.status:
        - name: /dev/xda1
        - maximum: 79%
        - minumum: 11%

It can be used with an ``onfail`` requisite, for example, to take additional
action in response to or in preparation for other states.

.. code-block:: sls

    storage_threshold:
      disk.status:
        - name: /dev/xda1
        - maximum: 97%

    clear_cache:
      cmd.run:
        - name: rm -r /var/cache/app
        - onfail:
          - disk: storage_threshold
'''
from __future__ import absolute_import

# Import salt libs
from salt.ext.six import string_types

__monitor__ = [
        'status',
        ]


def _validate_percent(name, value):
    '''
    Validate ``name`` as an integer in the range [0, 100]
    '''
    comment = ''
    # Must be integral
    try:
        if isinstance(value, string_types):
            value = value.strip('%')
        value = int(value)
    except (TypeError, ValueError):
        comment += '{0} must be an integer '.format(name)
    # Must be in percent range
    else:
        if value < 0 or value > 100:
            comment += '{0} must be in the range [0, 100] '.format(name)
    return value, comment


def status(name, maximum=None, minimum=None):
    '''
    Return the current disk usage stats for the named mount point

    name
        Filesystem with which to check used space

    minimum
        The required minimum amount of used space in percent

    maximum
        The required maximum amount of used space in percent
    '''
    # Monitoring state, no changes will be made so no test interface needed
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {},
           'data': {}}  # Data field for monitoring state

    data = __salt__['disk.usage']()

    # Validate name
    if name not in data:
        ret['result'] = False
        ret['comment'] += 'Named disk mount not present '
        return ret
    # Validate extrema
    if maximum:
        maximum, comment = _validate_percent('maximum', maximum)
        ret['comment'] += comment
    if minimum:
        minimum, comment = _validate_percent('minimum', minimum)
        ret['comment'] += comment
    if minimum is not None and maximum is not None:
        if minimum >= maximum:
            ret['comment'] += 'Min must be less than max '
    if ret['comment']:
        return ret

    capacity = int(data[name]['capacity'].strip('%'))
    ret['data'] = data[name]
    if minimum is not None:
        if capacity < minimum:
            ret['comment'] = 'Disk used space is below minimum of {0}% at {1}%'.format(
                    minimum, capacity)
            return ret
    if maximum is not None:
        if capacity > maximum:
            ret['comment'] = 'Disk used space is above maximum of {0}% at {1}%'.format(
                    maximum, capacity)
            return ret
    ret['comment'] = 'Disk in acceptable range'
    ret['result'] = True
    return ret
