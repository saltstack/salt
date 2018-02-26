# -*- coding: utf-8 -*-
'''
Module for editing power settings on macOS

 .. versionadded:: 2016.3.0
'''
# Import python libs
from __future__ import absolute_import

# Import salt libs
import salt.utils
import salt.utils.mac_utils
from salt.exceptions import SaltInvocationError
from salt.ext.six.moves import range

__virtualname__ = 'power'


def __virtual__():
    '''
    Only for macOS
    '''
    if not salt.utils.is_darwin():
        return (False, 'The mac_power module could not be loaded: '
                       'module only works on macOS systems.')

    return __virtualname__


def _validate_sleep(minutes):
    '''
    Helper function that validates the minutes parameter. Can be any number
    between 1 and 180. Can also be the string values "Never" and "Off".

    Because "On" and "Off" get converted to boolean values on the command line
    it will error if "On" is passed

    Returns: The value to be passed to the command
    '''
    # Must be a value between 1 and 180 or Never/Off
    if isinstance(minutes, str):
        if minutes.lower() in ['never', 'off']:
            return 'Never'
        else:
            msg = 'Invalid String Value for Minutes.\n' \
                  'String values must be "Never" or "Off".\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
    elif isinstance(minutes, bool):
        if minutes:
            msg = 'Invalid Boolean Value for Minutes.\n' \
                  'Boolean value "On" or "True" is not allowed.\n' \
                  'Salt CLI converts "On" to boolean True.\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
        else:
            return 'Never'
    elif isinstance(minutes, int):
        if minutes in range(1, 181):
            return minutes
        else:
            msg = 'Invalid Integer Value for Minutes.\n' \
                  'Integer values must be between 1 and 180.\n' \
                  'Passed: {0}'.format(minutes)
            raise SaltInvocationError(msg)
    else:
        msg = 'Unknown Variable Type Passed for Minutes.\n' \
              'Passed: {0}'.format(minutes)
        raise SaltInvocationError(msg)


def get_sleep():
    '''
    Displays the amount of idle time until the machine sleeps. Settings for
    Computer, Display, and Hard Disk are displayed.

    :return: A dictionary containing the sleep status for Computer, Display, and
    Hard Disk
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_sleep
    '''
    return {'Computer': get_computer_sleep(),
            'Display': get_display_sleep(),
            'Hard Disk': get_harddisk_sleep()}


def set_sleep(minutes):
    '''
    Sets the amount of idle time until the machine sleeps. Sets the same value
    for Computer, Display, and Hard Disk. Pass "Never" or "Off" for computers
    that should never sleep.

    :param minutes: Can be an integer between 1 and 180 or "Never" or "Off"
    :ptype: int, str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_sleep 120
        salt '*' power.set_sleep never
    '''
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setsleep {0}'.format(value)
    salt.utils.mac_utils.execute_return_success(cmd)

    state = []
    for check in (get_computer_sleep, get_display_sleep, get_harddisk_sleep):
        state.append(salt.utils.mac_utils.confirm_updated(
            value,
            check,
        ))
    return all(state)


def get_computer_sleep():
    '''
    Display the amount of idle time until the computer sleeps.

    :return: A string representing the sleep settings for the computer
    :rtype: str

    CLI Example:

    ..code-block:: bash

        salt '*' power.get_computer_sleep
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getcomputersleep')
    return salt.utils.mac_utils.parse_return(ret)


def set_computer_sleep(minutes):
    '''
    Set the amount of idle time until the computer sleeps. Pass "Never" of "Off"
    to never sleep.

    :param minutes: Can be an integer between 1 and 180 or "Never" or "Off"
    :ptype: int, str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_computer_sleep 120
        salt '*' power.set_computer_sleep off
    '''
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setcomputersleep {0}'.format(value)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        str(value),
        get_computer_sleep,
    )


def get_display_sleep():
    '''
    Display the amount of idle time until the display sleeps.

    :return: A string representing the sleep settings for the displey
    :rtype: str

    CLI Example:

    ..code-block:: bash

        salt '*' power.get_display_sleep
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getdisplaysleep')
    return salt.utils.mac_utils.parse_return(ret)


def set_display_sleep(minutes):
    '''
    Set the amount of idle time until the display sleeps. Pass "Never" of "Off"
    to never sleep.

    :param minutes: Can be an integer between 1 and 180 or "Never" or "Off"
    :ptype: int, str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_display_sleep 120
        salt '*' power.set_display_sleep off
    '''
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setdisplaysleep {0}'.format(value)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        str(value),
        get_display_sleep,
    )


def get_harddisk_sleep():
    '''
    Display the amount of idle time until the hard disk sleeps.

    :return: A string representing the sleep settings for the hard disk
    :rtype: str

    CLI Example:

    ..code-block:: bash

        salt '*' power.get_harddisk_sleep
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getharddisksleep')
    return salt.utils.mac_utils.parse_return(ret)


def set_harddisk_sleep(minutes):
    '''
    Set the amount of idle time until the harddisk sleeps. Pass "Never" of "Off"
    to never sleep.

    :param minutes: Can be an integer between 1 and 180 or "Never" or "Off"
    :ptype: int, str

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_harddisk_sleep 120
        salt '*' power.set_harddisk_sleep off
    '''
    value = _validate_sleep(minutes)
    cmd = 'systemsetup -setharddisksleep {0}'.format(value)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        str(value),
        get_harddisk_sleep,
    )


def get_wake_on_modem():
    '''
    Displays whether 'wake on modem' is on or off if supported

    :return: A string value representing the "wake on modem" settings
    :rtype: str

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_wake_on_modem
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getwakeonmodem')
    return salt.utils.mac_utils.validate_enabled(
        salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_wake_on_modem(enabled):
    '''
    Set whether or not the computer will wake from sleep when modem activity is
    detected.

    :param bool enabled: True to enable, False to disable. "On" and "Off" are
    also acceptable values. Additionally you can pass 1 and 0 to represent True
    and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_wake_on_modem True
    '''
    state = salt.utils.mac_utils.validate_enabled(enabled)
    cmd = 'systemsetup -setwakeonmodem {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        state,
        get_wake_on_modem,
    )


def get_wake_on_network():
    '''
    Displays whether 'wake on network' is on or off if supported

    :return: A string value representing the "wake on network" settings
    :rtype: string

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_wake_on_network
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getwakeonnetworkaccess')
    return salt.utils.mac_utils.validate_enabled(
        salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_wake_on_network(enabled):
    '''
    Set whether or not the computer will wake from sleep when network activity
    is detected.

    :param bool enabled: True to enable, False to disable. "On" and "Off" are
    also acceptable values. Additionally you can pass 1 and 0 to represent True
    and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_wake_on_network True
    '''
    state = salt.utils.mac_utils.validate_enabled(enabled)
    cmd = 'systemsetup -setwakeonnetworkaccess {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        state,
        get_wake_on_network,
    )


def get_restart_power_failure():
    '''
    Displays whether 'restart on power failure' is on or off if supported

    :return: A string value representing the "restart on power failure" settings
    :rtype: string

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_restart_power_failure
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getrestartpowerfailure')
    return salt.utils.mac_utils.validate_enabled(
        salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_restart_power_failure(enabled):
    '''
    Set whether or not the computer will automatically restart after a power
    failure.

    :param bool enabled: True to enable, False to disable. "On" and "Off" are
    also acceptable values. Additionally you can pass 1 and 0 to represent True
    and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_restart_power_failure True
    '''
    state = salt.utils.mac_utils.validate_enabled(enabled)
    cmd = 'systemsetup -setrestartpowerfailure {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        state,
        get_restart_power_failure,
    )


def get_restart_freeze():
    '''
    Displays whether 'restart on freeze' is on or off if supported

    :return: A string value representing the "restart on freeze" settings
    :rtype: string

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_restart_freeze
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getrestartfreeze')
    return salt.utils.mac_utils.validate_enabled(
        salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_restart_freeze(enabled):
    '''
    Specifies whether the server restarts automatically after a system freeze.
    This setting doesn't seem to be editable. The command completes successfully
    but the setting isn't actually updated. This is probably a macOS. The
    functions remains in case they ever fix the bug.

    :param bool enabled: True to enable, False to disable. "On" and "Off" are
    also acceptable values. Additionally you can pass 1 and 0 to represent True
    and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_restart_freeze True
    '''
    state = salt.utils.mac_utils.validate_enabled(enabled)
    cmd = 'systemsetup -setrestartfreeze {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        state,
        get_restart_freeze,
        True
    )


def get_sleep_on_power_button():
    '''
    Displays whether 'allow power button to sleep computer' is on or off if
    supported

    :return: A string value representing the "allow power button to sleep
    computer" settings
    :rtype: string

    CLI Example:

    .. code-block:: bash

        salt '*' power.get_sleep_on_power_button
    '''
    ret = salt.utils.mac_utils.execute_return_result(
        'systemsetup -getallowpowerbuttontosleepcomputer')
    return salt.utils.mac_utils.validate_enabled(
            salt.utils.mac_utils.parse_return(ret)) == 'on'


def set_sleep_on_power_button(enabled):
    '''
    Set whether or not the power button can sleep the computer.

    :param bool enabled: True to enable, False to disable. "On" and "Off" are
    also acceptable values. Additionally you can pass 1 and 0 to represent True
    and False respectively

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' power.set_sleep_on_power_button True
    '''
    state = salt.utils.mac_utils.validate_enabled(enabled)
    cmd = 'systemsetup -setallowpowerbuttontosleepcomputer {0}'.format(state)
    salt.utils.mac_utils.execute_return_success(cmd)

    return salt.utils.mac_utils.confirm_updated(
        state,
        get_sleep_on_power_button,
    )
