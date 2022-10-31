"""
Monitor temperature, humidity and pressure using the SenseHat of a Raspberry Pi
===============================================================================

.. versionadded:: 2017.7.0

:maintainer:    Benedikt Werner <1benediktwerner@gmail.com>
:maturity:      new
:depends:       sense_hat Python module
"""
import logging
import re

import salt.utils.beacons

log = logging.getLogger(__name__)

__virtualname__ = "sensehat"


def __virtual__():
    if "sensehat.get_pressure" in __salt__:
        return __virtualname__
    else:
        err_msg = "sensehat.get_pressure is missing."
        log.error("Unable to load %s beacon: %s", __virtualname__, err_msg)
        return False, err_msg


def validate(config):
    """
    Validate the beacon configuration
    """
    # Configuration for sensehat beacon should be a list
    if not isinstance(config, list):
        return False, "Configuration for sensehat beacon must be a list."
    else:
        config = salt.utils.beacons.list_to_dict(config)

        if "sensors" not in config:
            return False, "Configuration for sensehat beacon requires sensors."
    return True, "Valid beacon configuration"


def beacon(config):
    """
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
            - sensors:
                humidity: 70%
                temperature: [20, 40]
                temperature_from_pressure: 40
                pressure: 1500
    """
    ret = []
    min_default = {"humidity": "0", "pressure": "0", "temperature": "-273.15"}

    config = salt.utils.beacons.list_to_dict(config)

    for sensor in config.get("sensors", {}):
        sensor_function = "sensehat.get_{}".format(sensor)
        if sensor_function not in __salt__:
            log.error("No sensor for meassuring %s. Skipping.", sensor)
            continue

        sensor_config = config["sensors"][sensor]
        if isinstance(sensor_config, list):
            sensor_min = str(sensor_config[0])
            sensor_max = str(sensor_config[1])
        else:
            sensor_min = min_default.get(sensor, "0")
            sensor_max = str(sensor_config)

        if isinstance(sensor_min, str) and "%" in sensor_min:
            sensor_min = re.sub("%", "", sensor_min)
        if isinstance(sensor_max, str) and "%" in sensor_max:
            sensor_max = re.sub("%", "", sensor_max)
        sensor_min = float(sensor_min)
        sensor_max = float(sensor_max)

        current_value = __salt__[sensor_function]()
        if not sensor_min <= current_value <= sensor_max:
            ret.append({"tag": "sensehat/{}".format(sensor), sensor: current_value})

    return ret
