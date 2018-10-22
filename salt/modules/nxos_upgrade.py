# -*- coding: utf-8 -*-
'''
Execution module to upgrade Cisco NX-OS Switches.

.. versionadded:: xxxx.xx.x

This module supports execution using a Proxy Minion:
  Proxy Minion: Connect over SSH or NX-API HTTP(S).
  See :mod:`salt.proxy.nxos <salt.proxy.nxos>` for proxy minion setup details.

:maturity:   new
:platform:   nxos

.. note::

    To use this module over remote NX-API the feature must be enabled on the
    NX-OS device by executing ``feature nxapi`` in configuration mode.

    This is not required for NX-API over UDS.

    Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# feature nxapi

    To check that NX-API is properly enabled, execute ``show nxapi``.

    Output example:

    .. code-block:: bash

        switch# show nxapi
        nxapi enabled
        HTTPS Listen on port 443
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import logging
import difflib
import re
import ast

# Import Salt libs
from salt.utils.pycrypto import gen_hash, secure_password
import salt.utils.platform
import salt.utils.nxos
from salt.ext import six
from salt.exceptions import (NxosClientError, NxosCliError, NxosError,
                             NxosRequestNotSupported, CommandExecutionError)

__virtualname__ = 'nxos'
__virtual_aliases__ = ('nxos_upgrade',)

log = logging.getLogger(__name__)

DEVICE_DETAILS = {'grains_cache': {}}
COPY_RS = 'copy running-config startup-config'


def __virtual__():
    return __virtualname__


def check_upgrade_impact(system_image, kickstart_image=None, issu=True, **kwargs):
    '''
    Display upgrade impact information but don't perform upgrade.

    system_image (Mandatory Option)
        Path on bootflash: to system image upgrade file.

    kickstart_image
        Path on bootflash: to kickstart image upgrade file.
        (Not required if using combined system/kickstart image file)
        Default: None

    issu
        Set this option to True when an in service software service or
        non-disruptive upgrade is needed. The upgrade will abort if issu is
        not possible.
        Default: True

    timeout
        Timeout in seconds for long running 'install all' impact command.
        Default: 900

    error_pattern
        Use the option to pass in a regular expression to search for in the
        output of the 'install all impact' command that indicates an error
        has occurred.  This option is only used when proxy minion connection
        type is ssh and otherwise ignored.

    .. code-block:: bash

        salt 'n9k' nxos.upgrade_impact system_image=nxos.9.2.1.bin
        salt 'n7k' nxos.upgrade_impact system_image=n7000-s2-dk9.8.1.1.bin \\
            kickstart_image=n7000-s2-kickstart.8.1.1.bin issu=False
    '''
    si = system_image
    ki = kickstart_image
    dev = 'bootflash'
    cmd = 'terminal dont-ask ; show install all impact'

    if ki is not None:
        cmd = cmd + ' kickstart {0}:{1} system {0}:{2}'.format(dev, ki, si)
    else:
        cmd = cmd + ' nxos {0}:{1}'.format(dev, si)

    if issu:
        cmd = cmd + ' non-disruptive'

    log.info("Check upgrade impact using command: '{}'".format(cmd))
    kwargs.update({'timeout': 900})
    error_pattern_list = ['Another install procedure may be in progress']
    kwargs.update({'error_pattern': error_pattern_list})

    # Execute Upgrade Impact Check
    try:
        impact_check = __salt__['nxos.sendline'](cmd, **kwargs)
    except CommandExecutionError as e:
        return ast.literal_eval(e.message)
    return impact_check


def upgrade(system_image, kickstart_image=None, issu=True, **kwargs):
    '''
    Upgrade NX-OS switch.

    system_image (Mandatory Option)
        Path on bootflash: to system image upgrade file.

    kickstart_image
        Path on bootflash: to kickstart image upgrade file.
        (Not required if using combined system/kickstart image file)
        Default: None

    issu
        Set this option to True when an in service software service or
        non-disruptive upgrade is needed. The upgrade will abort if issu is
        not possible.
        Default: True

    timeout
        Timeout in seconds for long running 'install all' upgrade command.
        Default: 900

    error_pattern
        Use the option to pass in a regular expression to search for in the
        output of the 'install all upgrade command that indicates an error
        has occurred.  This option is only used when proxy minion connection
        type is ssh and otherwise ignored.

    .. code-block:: bash

        salt 'n9k' nxos.upgrade system_image=nxos.9.2.1.bin
        salt 'n7k' nxos.upgrade system_image=n7000-s2-dk9.8.1.1.bin \\
            kickstart_image=n7000-s2-kickstart.8.1.1.bin issu=False
    '''
    si = system_image
    ki = kickstart_image
    dev = 'bootflash'
    cmd = 'terminal dont-ask ; install all'

    if ki is None:
        logmsg = 'Upgrading device using combined system/kickstart image.'
        logmsg += '\nSystem Image: {}'.format(si)
        cmd = cmd + ' nxos {0}:{1}'.format(dev, si)
    else:
        logmsg = 'Upgrading device using separate system/kickstart images.'
        logmsg += '\nSystem Image: {}'.format(si)
        logmsg += '\nKickstart Image: {}'.format(ki)
        cmd = cmd + ' kickstart {0}:{1} system {0}:{2}'.format(dev, ki, si)

    if issu:
        logmsg += '\nIn Service Software Upgrade/Downgrade (non-disruptive) requested.'
        cmd = cmd + ' non-disruptive'
    else:
        logmsg += '\nDisruptive Upgrade/Downgrade requested.'

    log.info(logmsg)
    log.info("Begin upgrade using command: '{}'".format(cmd))

    kwargs.update({'timeout': 900})
    error_pattern_list = ['Another install procedure may be in progress']
    kwargs.update({'error_pattern': error_pattern_list})

    # Begin Upgrade
    try:
        upgrade_result = __salt__['nxos.sendline'](cmd, **kwargs)
    except CommandExecutionError as e:
        return ast.literal_eval(e.message)
    return upgrade_result
