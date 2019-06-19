# -*- coding: utf-8 -*-
'''
Read lm-sensors

.. versionadded:: 2014.1.3
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import python libs
import logging

# import Salt libs
import salt.utils.path


log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which('sensors'):
        return True
    return (False, 'sensors does not exist in the path')


def sense(chip, fahrenheit=False):
    '''
    Gather lm-sensors data from a given chip

    To determine the chip to query, use the 'sensors' command
    and see the leading line in the block.

    Example:

    /usr/bin/sensors

    coretemp-isa-0000
    Adapter: ISA adapter
    Physical id 0:  +56.0°C  (high = +87.0°C, crit = +105.0°C)
    Core 0:         +52.0°C  (high = +87.0°C, crit = +105.0°C)
    Core 1:         +50.0°C  (high = +87.0°C, crit = +105.0°C)
    Core 2:         +56.0°C  (high = +87.0°C, crit = +105.0°C)
    Core 3:         +53.0°C  (high = +87.0°C, crit = +105.0°C)

    Given the above, the chip is 'coretemp-isa-0000'.
    '''
    extra_args = ''
    if fahrenheit is True:
        extra_args = '-f'
    sensors = __salt__['cmd.run']('/usr/bin/sensors {0} {1}'.format(chip, extra_args), python_shell=False).splitlines()
    ret = {}
    for sensor in sensors:
        sensor_list = sensor.split(':')
        if len(sensor_list) >= 2:
            ret[sensor_list[0]] = sensor_list[1].lstrip()
    return ret
