# -*- coding: utf-8 -*-
'''
This module contains the function calls to execute command line scripts
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys
import time
import logging
import threading
import traceback
from random import randint

# Import salt libs
from salt import cloud, defaults

from salt.exceptions import SaltSystemExit, SaltClientError, SaltReqTimeoutError
import salt.defaults.exitcodes  # pylint: disable=unused-import

log = logging.getLogger(__name__)


def _handle_interrupt(exc, original_exc, hardfail=False, trace=''):
    '''
    if hardfailing:
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
    import salt.cli.daemons
    master = salt.cli.daemons.Master()
    master.start()


def minion_process():
    '''
    Start a minion process
    '''
    import salt.utils
    import salt.cli.daemons
    # salt_minion spawns this function in a new process

    salt.utils.appendproctitle('KeepAlive')

    def suicide_when_without_parent(parent_pid):
        '''
        Have the minion suicide if the parent process is gone

        NOTE: small race issue where the parent PID could be replace
        with another process with same PID!
        '''
        while True:
            time.sleep(5)
            try:
                # check pid alive (Unix only trick!)
                if os.getuid() == 0 and not salt.utils.is_windows():
                    os.kill(parent_pid, 0)
            except OSError as exc:
                # forcibly exit, regular sys.exit raises an exception-- which
                # isn't sufficient in a thread
                log.error('Minion process encountered exception: {0}'.format(exc))
                os._exit(salt.defaults.exitcodes.EX_GENERIC)

    if not salt.utils.is_windows():
        thread = threading.Thread(target=suicide_when_without_parent, args=(os.getppid(),))
        thread.start()

    minion = salt.cli.daemons.Minion()

    try:
        minion.start()
    except (SaltClientError, SaltReqTimeoutError, SaltSystemExit) as exc:
        log.warning('Fatal functionality error caught by minion handler:\n', exc_info=True)
        log.warning('** Restarting minion **')
        delay = 60
        if minion is not None and hasattr(minion, 'config'):
            delay = minion.config.get('random_reauth_delay', 60)
        delay = randint(1, delay)
        log.info('waiting random_reauth_delay {0}s'.format(delay))
        time.sleep(delay)
        exit(salt.defaults.exitcodes.SALT_KEEPALIVE)


def salt_minion():
    '''
    Start the salt minion in a subprocess.
    Auto restart minion on error.
    '''
    import signal
    import functools
    import salt.cli.daemons
    import multiprocessing
    if '' in sys.path:
        sys.path.remove('')

    if salt.utils.is_windows():
        minion = salt.cli.daemons.Minion()
        minion.start()
        return

    if '--disable-keepalive' in sys.argv:
        sys.argv.remove('--disable-keepalive')
        minion = salt.cli.daemons.Minion()
        minion.start()
        return

    def escalate_signal_to_process(pid, signum, sigframe):  # pylint: disable=unused-argument
        '''
        Escalate the signal received to the multiprocessing process that
        is actually running the minion
        '''
        # escalate signal
        os.kill(pid, signum)

    # keep one minion subprocess running
    prev_sigint_handler = signal.getsignal(signal.SIGINT)
    prev_sigterm_handler = signal.getsignal(signal.SIGTERM)
    while True:
        try:
            process = multiprocessing.Process(target=minion_process)
            process.start()
            signal.signal(signal.SIGTERM,
                          functools.partial(escalate_signal_to_process,
                                            process.pid))
            signal.signal(signal.SIGINT,
                          functools.partial(escalate_signal_to_process,
                                            process.pid))
        except Exception:  # pylint: disable=broad-except
            # if multiprocessing does not work
            minion = salt.cli.daemons.Minion()
            minion.start()
            break

        process.join()

        # Process exited or was terminated. Since we're going to try to restart
        # it, we MUST, reset signal handling to the previous handlers
        signal.signal(signal.SIGINT, prev_sigint_handler)
        signal.signal(signal.SIGTERM, prev_sigterm_handler)

        if not process.exitcode == salt.defaults.exitcodes.SALT_KEEPALIVE:
            sys.exit(process.exitcode)
        # ontop of the random_reauth_delay already preformed
        # delay extra to reduce flooding and free resources
        # NOTE: values are static but should be fine.
        time.sleep(2 + randint(1, 10))
        # need to reset logging because new minion objects
        # cause extra log handlers to accumulate
        rlogger = logging.getLogger()
        for handler in rlogger.handlers:
            rlogger.removeHandler(handler)
        logging.basicConfig()


def proxy_minion_process(queue):
    '''
    Start a proxy minion process
    '''
    import salt.cli.daemons
    # salt_minion spawns this function in a new process

    def suicide_when_without_parent(parent_pid):
        '''
        Have the minion suicide if the parent process is gone

        NOTE: there is a small race issue where the parent PID could be replace
        with another process with the same PID!
        '''
        while True:
            time.sleep(5)
            try:
                # check pid alive (Unix only trick!)
                os.kill(parent_pid, 0)
            except OSError:
                # forcibly exit, regular sys.exit raises an exception-- which
                # isn't sufficient in a thread
                os._exit(999)

    if not salt.utils.is_windows():
        thread = threading.Thread(target=suicide_when_without_parent, args=(os.getppid(),))
        thread.start()

    restart = False
    proxyminion = None
    try:
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
    except (Exception, SaltClientError, SaltReqTimeoutError, SaltSystemExit) as exc:
        log.error('Proxy Minion failed to start: ', exc_info=True)
        restart = True
    except SystemExit as exc:
        restart = False

    if restart is True:
        log.warning('** Restarting proxy minion **')
        delay = 60
        if proxyminion is not None:
            if hasattr(proxyminion, 'config'):
                delay = proxyminion.config.get('random_reauth_delay', 60)
        random_delay = randint(1, delay)
        log.info('Sleeping random_reauth_delay of {0} seconds'.format(random_delay))
        # preform delay after minion resources have been cleaned
        queue.put(random_delay)
    else:
        queue.put(0)


def salt_proxy_minion():
    '''
    Start a proxy minion.
    '''
    import salt.cli.daemons
    import multiprocessing
    if '' in sys.path:
        sys.path.remove('')

    if salt.utils.is_windows():
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
        return

    if '--disable-keepalive' in sys.argv:
        sys.argv.remove('--disable-keepalive')
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
        return

    # keep one minion subprocess running
    while True:
        try:
            queue = multiprocessing.Queue()
        except Exception:
            # This breaks in containers
            proxyminion = salt.cli.daemons.ProxyMinion()
            proxyminion.start()
            return
        process = multiprocessing.Process(target=proxy_minion_process, args=(queue,))
        process.start()
        try:
            process.join()
            try:
                restart_delay = queue.get(block=False)
            except Exception:
                if process.exitcode == 0:
                    # Minion process ended naturally, Ctrl+C or --version
                    break
                restart_delay = 60
            if restart_delay == 0:
                # Minion process ended naturally, Ctrl+C, --version, etc.
                break
            # delay restart to reduce flooding and allow network resources to close
            time.sleep(restart_delay)
        except KeyboardInterrupt:
            break
        # need to reset logging because new minion objects
        # cause extra log handlers to accumulate
        rlogger = logging.getLogger()
        for handler in rlogger.handlers:
            rlogger.removeHandler(handler)
        logging.basicConfig()


def salt_syndic():
    '''
    Start the salt syndic.
    '''
    import salt.cli.daemons
    pid = os.getpid()
    try:
        syndic = salt.cli.daemons.Syndic()
        syndic.start()
    except KeyboardInterrupt:
        os.kill(pid, 15)


def salt_key():
    '''
    Manage the authentication keys with salt-key.
    '''
    import salt.cli.key
    client = None
    try:
        client = salt.cli.key.SaltKey()
        client.run()
    except KeyboardInterrupt as err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)
    except Exception as err:
        sys.stderr.write("Error: {0}\n".format(err.message))


def salt_cp():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    import salt.cli.cp
    client = None
    try:
        client = salt.cli.cp.SaltCPCli()
        client.run()
    except KeyboardInterrupt as err:
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
    import salt.cli.call
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.call.SaltCall()
        client.run()
    except KeyboardInterrupt as err:
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
    import salt.cli.run
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.run.SaltRun()
        client.run()
    except KeyboardInterrupt as err:
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
    import salt.cli.ssh
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.ssh.SaltSSH()
        client.run()
    except KeyboardInterrupt as err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)
    except SaltClientError as err:
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
    try:
        import salt.cloud.cli
        has_saltcloud = True
    except ImportError as e:
        log.error("Error importing salt cloud {0}".format(e))
        # No salt cloud on Windows
        has_saltcloud = False
    if '' in sys.path:
        sys.path.remove('')

    if not has_saltcloud:
        print('salt-cloud is not available in this system')
        sys.exit(defaults.exitcodes.EX_UNAVAILABLE)

    client = None
    try:
        client = cloud.cli.SaltCloud()
        client.run()
    except KeyboardInterrupt as err:
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
    import salt.cli.api
    sapi = salt.cli.api.SaltAPI()  # pylint: disable=E1120
    sapi.start()


def salt_main():
    '''
    Publish commands to the salt system from the command line on the
    master.
    '''
    import salt.cli.salt
    if '' in sys.path:
        sys.path.remove('')
    client = None
    try:
        client = salt.cli.salt.SaltCMD()
        client.run()
    except KeyboardInterrupt as err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(
            SystemExit('\nExiting gracefully on Ctrl-c'),
            err,
            hardcrash, trace=trace)


def salt_spm():
    '''
    The main function for spm, the Salt Package Manager

    .. versionadded:: 2015.8.0
    '''
    import salt.cli.spm
    spm = salt.cli.spm.SPM()  # pylint: disable=E1120
    spm.run()
