# -*- coding: utf-8 -*-
'''
Management of logs using Solaris logadm.

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.modulus.logadm
:platform:      Oracle Solaris, Sun Solaris, illumos

.. versionadded:: nitrogen

.. code-block:: yaml

    .. note::
        TODO

'''
from __future__ import absolute_import

# Import Python libs
import logging

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'logadm'


def __virtual__():
    '''
    Provides logadm state if we have the module
    '''
    if 'logadm.list_conf' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only if the logadm execution module is present'.format(
                __virtualname__
            )
        )


def config_present(name, value):
    '''
    Ensure configuration property is set to value in /usbkey/config

    name : string
        name of property
    value : string
        value of property

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    ret['comment'] = 'TODO'
    return ret


def config_absent(name, log_file=None):
    '''
    Ensure configuration for log file is absent

    name : string
        entryname
    log_file : string
        (optional) log file path

    .. note::
        If log_file is specified it will be used instead of the entry name.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    ## retrieve all log configuration
    config = __salt__['logadm.list_conf']()

    ## figure out log_file and name
    if not log_file:
        if name.startswith('/'):
            log_file = name
            name = None
        else:
            for log in config:
                if 'entryname' in config[log] and config[log]['entryname'] == name:
                    log_file = config[log]['log_file']
                    break
    if not name:
        for log in config:
            if 'log_file' in config[log] and config[log]['log_file'] == log_file:
                if 'entryname' in config[log]:
                    name = config[log]['entryname']
                break

    ## remove log if needed
    if log_file in config:
        res = __salt__['logadm.remove'](name if name else log_file)
        ret['result'] = 'Error' not in res
        if ret['result']:
            ret['comment'] = 'Configuration for {} removed.'.format(log_file)
            ret['changes'][log_file] = None
        else:
            ret['comment'] = res['Error']
    else:
        ret['result'] = True
        ret['comment'] = 'No configuration for {} present.'.format(log_file)

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
