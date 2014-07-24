# -*- coding: utf-8 -*-
'''
This module contains the function calls to execute command line scripts
'''

# Import python libs
from __future__ import print_function
import os
import sys
import traceback
import logging
import multiprocessing
import threading
import signal
import time
from random import randint

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
    Start the salt master.
    '''
    master = salt.Master()
    master.start()


def salt_minion():
    '''
    Start the salt minion.
    '''
    if '' in sys.path:
        sys.path.remove('')

    # disabled keepalive mode on Windows systems because 
    # suicide_without_parent is posix only
    if '--disable-keepalive' in sys.argv or salt.utils.is_windows():
        sys.argv.remove('--disable-keepalive')
        minion = salt.Minion()
        minion.start()
    else:
        if '-d' in sys.argv or '--daemon' in sys.argv:
            # disable daemonize on sub proccesses
            if '-d' in sys.argv:
                sys.argv.remove('-d')
            if '--daemon' in sys.argv:
                sys.argv.remove('--daemon')
            # daemonize current process
            salt.utils.daemonize()

        def minion_process(q, parent_pid):
            def suicide_without_parent(parent_pid, my_pid):
                while True:
                    time.sleep(2)
                    try:
                        # check pid alive (wont work on Windows)
                        os.kill(parent_pid, 0)
                    except OSError:
                        os.kill(my_pid, signal.SIGTERM)
            t = threading.Thread(target=suicide_without_parent, args=(parent_pid, os.getpid(),))
            t.start()

            # new minions creates globals that are tricky to cleanup.
            # running the minion in a new process/thread forces good cleanup
            minion = None
            try:
                minion = salt.Minion()
                minion.start()
                q.put(0)
            except Exception, err:
                log.error(err)
                log.warn('** Restarting minion **')
                delay = 60
                if minion is None:
                    if hasattr(minion, 'config'):
                        delay = minion.config.get('random_reauth_delay', 60)
                random_delay = randint(1, delay)
                log.info('Sleeping random_reauth_delay of {0} seconds'.format(random_delay))
                # preform delay after minion resources have been cleaned
                q.put(random_delay)
            finally:
                t.terminate()

        while True:
            #import threading
            #import Queue
            #q = Queue.Queue()
            #proc = threading.Thread(target=minion_process, args=(q,))
            q = multiprocessing.Queue()
            proc = multiprocessing.Process(target=minion_process, args=(q, os.getppid(), ))
            proc.start()
            try:
                proc.join()
            except KeyboardInterrupt, err:
                return 0

            restart_delay = q.get()
            if restart_delay == 0:
                break
            time.sleep(restart_delay)

            # when starting minion in new process we need to reset logging because
            # creating a new minion object will cause extra log handlers to accumulate
            rlogger = logging.getLogger()
            for h in rlogger.handlers:
                rlogger.removeHandler(h)
            logging.basicConfig()


def salt_syndic():
    '''
    Start the salt syndic.
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


def salt_api():
    '''
    The main function for salt-api
    '''
    sapi = salt.cli.SaltAPI()
    sapi.run()


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
