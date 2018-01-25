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

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
import salt.utils.args
import salt.utils.data

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


def rotate(name, **kwargs):
    '''
    Add a log to the logadm configuration

    name : string
        alias for entryname
    **kwargs : boolean|string|int
        optional additional flags and parameters

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    # cleanup kwargs
    kwargs = salt.utils.args.clean_kwargs(**kwargs)

    # inject name as entryname
    if 'entryname' not in kwargs:
        kwargs['entryname'] = name

    # figure out log_file and entryname
    if 'log_file' not in kwargs or not kwargs['log_file']:
        if 'entryname' in kwargs and kwargs['entryname']:
            if kwargs['entryname'].startswith('/'):
                kwargs['log_file'] = kwargs['entryname']

    # check for log_file
    if 'log_file' not in kwargs or not kwargs['log_file']:
        ret['result'] = False
        ret['comment'] = 'Missing log_file attribute!'
    else:
        # lookup old configuration
        old_config = __salt__['logadm.list_conf']()

        # remove existing entry
        if kwargs['log_file'] in old_config:
            res = __salt__['logadm.remove'](kwargs['entryname'] if 'entryname' in kwargs else kwargs['log_file'])
            ret['result'] = 'Error' not in res
            if not ret['result']:
                ret['comment'] = res['Error']
                ret['changes'] = {}

        # add new entry
        res = __salt__['logadm.rotate'](name, **kwargs)
        ret['result'] = 'Error' not in res
        if ret['result']:
            new_config = __salt__['logadm.list_conf']()
            ret['comment'] = 'Log configuration {}'.format('updated' if kwargs['log_file'] in old_config else 'added')
            if kwargs['log_file'] in old_config:
                for key, val in salt.utils.data.compare_dicts(old_config[kwargs['log_file']], new_config[kwargs['log_file']]).items():
                    ret['changes'][key] = val['new']
            else:
                ret['changes'] = new_config[kwargs['log_file']]
            log.debug(ret['changes'])
        else:
            ret['comment'] = res['Error']
            # NOTE: we need to remove the log file first
            #       potentially the log configuraiton can get lost :s
            if kwargs['log_file'] in old_config:
                ret['changes'] = {kwargs['log_file']: None}
            else:
                ret['changes'] = {}

    return ret


def remove(name, log_file=None):
    '''
    Remove a log from the logadm configuration

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

    # retrieve all log configuration
    config = __salt__['logadm.list_conf']()

    # figure out log_file and name
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

    # remove log if needed
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
