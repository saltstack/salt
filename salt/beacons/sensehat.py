# -*- coding: utf-8 -*-
'''
Beacon to monitor temperature, humidity and pressure using the SenseHat
of a Raspberry Pi.

:maintainer:    Benedikt Werner <1benediktwerner@gmail.com>
:maturity:      new
:depends:       sense_hat Python module
'''

from __future__ import absolute_import
import logging
import re

log = logging.getLogger(__name__)


def __virtual__():
    return 'sensehat.get_pressure' in __salt__


def __validate__(config):
    '''
    Validate the beacon configuration
    '''
    # Configuration for sensehat beacon should be a dict
    if not isinstance(config, dict):
        return False, ('Configuration for sensehat beacon '
                       'must be a dictionary.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Monitor the temperature, humidity and pressure using the SenseHat sensors.

    You can either specify a threshold for each value and only emit a beacon
    if it is exceeded or define a range and emit a beacon when the value is
    out of range.

    Units:
    * humidity:                     percent
    * temperature:                  degrees Celsius
    * temperature_from_pressure:    degrees Celsius
    * pressure:                     Millibars

    .. code-block:: yaml

        beacons:
          sensehat:
            humidity: 70%
            temperature: [20, 40]
            temperature_from_pressure: 40
            pressure: 1500
    '''
    ret = []
    min_default = {
        'humidity': '0',
        'pressure': '0',
        'temperature': '-273.15'
    }

    for sensor in config:
        sensor_function = 'sensehat.get_{0}'.format(sensor)
        if sensor_function not in __salt__:
            log.error('No sensor for meassuring {0}. Skipping.'.format(sensor))
            continue

        sensor_config = config[sensor]
        if isinstance(sensor_config, list):
            sensor_min = str(sensor_config[0])
            sensor_max = str(sensor_config[1])
        else:
            sensor_min = min_default.get(sensor, '0')
            sensor_max = str(sensor_config)

        if '%' in sensor_min:
            sensor_min = re.sub('%', '', sensor_min)
        if '%' in sensor_max:
            sensor_max = re.sub('%', '', sensor_max)
        sensor_min = float(sensor_min)
        sensor_max = float(sensor_max)

        current_value = __salt__[sensor_function]()
        if not sensor_min <= current_value <= sensor_max:
            ret.append({
                'tag': 'sensehat/{0}'.format(sensor),
                sensor: current_value
            })

    return ret
