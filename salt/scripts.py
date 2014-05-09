# -*- coding: utf-8 -*-
'''
This module contains the function calls to execute command line scripts
'''

# Import python libs
from __future__ import print_function
import os
import sys
import time

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
    try:
        saltkey = salt.cli.SaltKey()
        saltkey.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')


def salt_cp():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    try:
        cp_ = salt.cli.SaltCP()
        cp_.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')


def salt_call():
    '''
    Directly call a salt command in the modules, does not require a running
    salt minion to run.
    '''
    if '' in sys.path:
        sys.path.remove('')
    try:
        client = salt.cli.SaltCall()
        client.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')


def salt_run():
    '''
    Execute a salt convenience routine.
    '''
    if '' in sys.path:
        sys.path.remove('')
    try:
        client = salt.cli.SaltRun()
        client.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')


def salt_ssh():
    '''
    Execute the salt-ssh system
    '''
    if '' in sys.path:
        sys.path.remove('')
    try:
        client = salt.cli.SaltSSH()
        client.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')
    except salt.exceptions.SaltClientError as err:
        raise SystemExit(err)


def salt_cloud():
    '''
    The main function for salt-cloud
    '''
    if '' in sys.path:
        sys.path.remove('')

    if not HAS_SALTCLOUD:
        print('salt-cloud is not available in this system')
        sys.exit(os.EX_UNAVAILABLE)

    try:
        cloud = salt.cloud.cli.SaltCloud()
        cloud.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')


def salt_main():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    if '' in sys.path:
        sys.path.remove('')
    try:
        #import wingdbstub
        client = salt.cli.SaltCMD()
        client.run()
    except KeyboardInterrupt:
        raise SystemExit('\nExiting gracefully on Ctrl-c')
