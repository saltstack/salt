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
        - minimum: 11%

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

To use kilobytes (KB) for ``minimum`` and ``maximum`` rather than percents,
specify the ``absolute`` flag:

.. code-block:: sls

    used_space:
      disk.status:
        - name: /dev/xda1
        - minimum: 1024 KB
        - maximum: 1048576 KB
        - absolute: True
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
from salt.ext.six import string_types

__monitor__ = [
        'status',
        ]


def _validate_int(name, value, limits=(), strip='%'):
    '''
    Validate the named integer within the supplied limits inclusive and
    strip supplied unit characters
    '''
    comment = ''
    # Must be integral
    try:
        if isinstance(value, string_types):
            value = value.strip(' ' + strip)
        value = int(value)
    except (TypeError, ValueError):
        comment += '{0} must be an integer '.format(name)
    # Must be in range
    else:
        if len(limits) == 2:
            if value < limits[0] or value > limits[1]:
                comment += '{0} must be in the range [{1[0]}, {1[1]}] '.format(name, limits)
    return value, comment


def status(name, maximum=None, minimum=None, absolute=False):
    '''
    Return the current disk usage stats for the named mount point

    name
        Disk mount with which to check used space

    maximum
        The maximum disk utilization

    minimum
        The minimum disk utilization

    absolute
        By default, the utilization is measured in percentage. Set
        the `absolute` flag to use kilobytes.

        .. versionadded:: 2016.11.0
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
    if maximum is not None:
        if not absolute:
            maximum, comment = _validate_int('maximum', maximum, [0, 100])
        else:
            maximum, comment = _validate_int('maximum', maximum, strip='KB')
        ret['comment'] += comment
    if minimum is not None:
        if not absolute:
            minimum, comment = _validate_int('minimum', minimum, [0, 100])
        else:
            minimum, comment = _validate_int('minimum', minimum, strip='KB')
        ret['comment'] += comment
    if minimum is not None and maximum is not None:
        if minimum >= maximum:
            ret['comment'] += 'minimum must be less than maximum '
    if ret['comment']:
        return ret

    # Get used space
    if absolute:
        used = int(data[name]['used'])
    else:
        # POSIX-compliant df output reports percent used as 'capacity'
        used = int(data[name]['capacity'].strip('%'))

    # Collect return information
    ret['data'] = data[name]
    unit = 'KB' if absolute else '%'
    if minimum is not None:
        if used < minimum:
            ret['comment'] = ('Disk used space is below minimum'
                              ' of {0} {2} at {1} {2}'
                              ''.format(minimum, used, unit)
                             )
            return ret
    if maximum is not None:
        if used > maximum:
            ret['comment'] = ('Disk used space is above maximum'
                              ' of {0} {2} at {1} {2}'
                              ''.format(maximum, used, unit)
                             )
            return ret
    ret['comment'] = 'Disk used space in acceptable range'
    ret['result'] = True
    return ret
