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
    if name not in data:
        ret['result'] = False
        ret['comment'] += 'Named disk mount not present '
        return ret
    if maximum:
        try:
            if isinstance(maximum, string_types):
                maximum = int(maximum.strip('%'))
        except Exception:
            ret['comment'] += 'Max argument must be an integer '
    if minimum:
        try:
            if isinstance(minimum, string_types):
                minimum = int(minimum.strip('%'))
        except Exception:
            ret['comment'] += 'Min argument must be an integer '
    if minimum and maximum:
        if minimum >= maximum:
            ret['comment'] += 'Min must be less than max'
    if ret['comment']:
        return ret
    capacity = int(data[name]['capacity'].strip('%'))
    ret['data'] = data[name]
    if minimum:
        if capacity < minimum:
            ret['comment'] = 'Disk used space is below minimum of {0} at {1}'.format(
                    minimum, capacity)
            return ret
    if maximum:
        if capacity > maximum:
            ret['comment'] = 'Disk used space is above maximum of {0} at {1}'.format(
                    maximum, capacity)
            return ret
    ret['comment'] = 'Disk in acceptable range'
    ret['result'] = True
    return ret
