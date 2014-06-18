# -*- coding: utf-8 -*-
'''
This module contains the function calls to execute command line scripts
'''

# Import python libs
from __future__ import print_function
import os
import sys
import time
import traceback
import logging

# Import salt libs
import salt
import salt.exceptions
import salt.cli
try:
    import salt.cloud.cli
    HAS_SALTCLOUD = True
except ImportError:
    # No salt cloud on Windows
    HAS_SALTCLOUD = False


log = logging.getLogger(__name__)


def _handle_interrupt(exc, original_exc, hardfail=False, trace=''):
    '''
    if hardfalling:
        If we got the original stacktrace, log it
        If all cases, raise the original exception
        but this is logically part the initial
        stack.
    else just let salt exit gracefully

    '''
    if hardfail:
        if trace:
            log.error(trace)
        raise original_exc
    else:
        raise exc


def salt_master():
    '''
    Start the salt-master.
    '''
    master = salt.Master()
    master.start()


def salt_minion():
    '''
    Kick off a salt minion daemon.
    '''
    if '' in sys.path:
        sys.path.remove('')

    reconnect = True
    while reconnect:
        reconnect = False
        minion = salt.Minion()
        ret = minion.start()
        if ret == 'reconnect':
            del minion
            minion = None
            #### TODO: this dont seem to clear out the parsers.MinionOptionParser 
            #### in __init__ : class Minion(parsers.MinionOptionParser):
            #### this leads issues in utils/parsers.py LogLevelMixIn: process_log_level()
            #### because _mixin_after_parsed_funcs gets extra appended values on each restart.
            # give extra time for resources like ZMQ to close.
            time.sleep(10)
            reconnect = True


def salt_syndic():
    '''
    Kick off a salt syndic daemon.
    '''
    pid = os.getpid()
    try:
        syndic = salt.Syndic()
        syndic.start()
    except KeyboardInterrupt:
        os.kill(pid, 15)


def salt_key():
    '''
    Manage the authentication keys with salt-key.
    '''
    client = None
    try:
        client = salt.cli.SaltKey()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_cp():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    client = None
    try:
        client = salt.cli.SaltCP()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_call():
    '''
    Directly call a salt command in the modules, does not require a running
    salt minion to run.
    '''
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.SaltCall()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_run():
    '''
    Execute a salt convenience routine.
    '''
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.SaltRun()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_ssh():
    '''
    Execute the salt-ssh system
    '''
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.SaltSSH()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)
    except salt.exceptions.SaltClientError as err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit(err),
            err,
            hardcrash, trace=trace)


def salt_cloud():
    '''
    The main function for salt-cloud
    '''
    if '' in sys.path:
        sys.path.remove('')

    if not HAS_SALTCLOUD:
        print('salt-cloud is not available in this system')
        sys.exit(os.EX_UNAVAILABLE)

    client = None
    try:
        client = salt.cloud.cli.SaltCloud()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_main():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.SaltCMD()
        client.run()
    except KeyboardInterrupt, err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)
