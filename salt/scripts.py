# -*- coding: utf-8 -*-
"""
This module contains the function calls to execute command line scripts
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import functools
import logging
import os
import signal
import sys
import threading
import time
import traceback
from random import randint

import salt.defaults.exitcodes  # pylint: disable=unused-import
import salt.ext.six as six

# Import salt libs
from salt.exceptions import SaltClientError, SaltReqTimeoutError, SaltSystemExit

log = logging.getLogger(__name__)


def _handle_interrupt(exc, original_exc, hardfail=False, trace=""):
    """
    if hardfailing:
        If we got the original stacktrace, log it
        If all cases, raise the original exception
        but this is logically part the initial
        stack.
    else just let salt exit gracefully

    """
    if hardfail:
        if trace:
            log.error(trace)
        raise original_exc
    else:
        raise exc


def _handle_signals(client, signum, sigframe):
    try:
        # This raises AttributeError on Python 3.4 and 3.5 if there is no current exception.
        # Ref: https://bugs.python.org/issue23003
        trace = traceback.format_exc()
    except AttributeError:
        trace = ""
    try:
        hardcrash = client.options.hard_crash
    except (AttributeError, KeyError):
        hardcrash = False

    if signum == signal.SIGINT:
        exit_msg = "\nExiting gracefully on Ctrl-c"
        try:
            jid = client.local_client.pub_data["jid"]
            exit_msg += (
                "\n"
                "This job's jid is: {0}\n"
                "The minions may not have all finished running and any remaining "
                "minions will return upon completion. To look up the return data "
                "for this job later, run the following command:\n\n"
                "salt-run jobs.lookup_jid {0}".format(jid)
            )
        except (AttributeError, KeyError):
            pass
    else:
        exit_msg = None

    _handle_interrupt(
        SystemExit(exit_msg),
        Exception("\nExiting with hard crash on Ctrl-c"),
        hardcrash,
        trace=trace,
    )


def _install_signal_handlers(client):
    # Install the SIGINT/SIGTERM handlers if not done so far
    if signal.getsignal(signal.SIGINT) is signal.SIG_DFL:
        # No custom signal handling was added, install our own
        signal.signal(signal.SIGINT, functools.partial(_handle_signals, client))

    if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
        # No custom signal handling was added, install our own
        signal.signal(signal.SIGINT, functools.partial(_handle_signals, client))


def salt_master():
    """
    Start the salt master.
    """
    import salt.cli.daemons

    # Fix for setuptools generated scripts, so that it will
    # work with multiprocessing fork emulation.
    # (see multiprocessing.forking.get_preparation_data())
    if __name__ != "__main__":
        sys.modules["__main__"] = sys.modules[__name__]

    # REMOVEME after Python 2.7 support is dropped (also the six import)
    if six.PY2:
        from salt.utils.versions import warn_until

        # Message borrowed from pip's deprecation warning
        warn_until(
            "Sodium",
            "Python 2.7 will reach the end of its life on January 1st,"
            " 2020. Please upgrade your Python as Python 2.7 won't be"
            " maintained after that date.  Salt will drop support for"
            " Python 2.7 in the Sodium release or later.",
        )
    # END REMOVEME
    master = salt.cli.daemons.Master()
    master.start()


def minion_process():
    """
    Start a minion process
    """
    import salt.utils.platform
    import salt.utils.process
    import salt.cli.daemons

    # salt_minion spawns this function in a new process

    salt.utils.process.appendproctitle("KeepAlive")

    def handle_hup(manager, sig, frame):
        manager.minion.reload()

    lock = threading.RLock()

    def suicide_when_without_parent(parent_pid):
        """
        Have the minion suicide if the parent process is gone

        NOTE: small race issue where the parent PID could be replace
        with another process with same PID!
        """
        while lock.acquire(blocking=False):
            lock.release()
            time.sleep(5)
            try:
                # check pid alive (Unix only trick!)
                if os.getuid() == 0 and not salt.utils.platform.is_windows():
                    os.kill(parent_pid, 0)
            except OSError as exc:
                # forcibly exit, regular sys.exit raises an exception-- which
                # isn't sufficient in a thread
                log.error("Minion process encountered exception: %s", exc)
                os._exit(salt.defaults.exitcodes.EX_GENERIC)

    try:
        if not salt.utils.platform.is_windows():
            thread = threading.Thread(
                target=suicide_when_without_parent, args=(os.getppid(),)
            )
            thread.start()

        minion = salt.cli.daemons.Minion()
        signal.signal(signal.SIGHUP, functools.partial(handle_hup, minion))
        minion.start()
    except (SaltClientError, SaltReqTimeoutError, SaltSystemExit) as exc:
        lock.acquire(blocking=True)
        log.warning(
            "Fatal functionality error caught by minion handler:\n", exc_info=True
        )
        log.warning("** Restarting minion **")
        delay = 60
        if minion is not None and hasattr(minion, "config"):
            delay = minion.config.get("random_reauth_delay", 60)
        delay = randint(1, delay)
        log.info("waiting random_reauth_delay %ss", delay)
        time.sleep(delay)
        sys.exit(salt.defaults.exitcodes.SALT_KEEPALIVE)
    finally:
        lock.acquire(blocking=True)


def salt_minion():
    """
    Start the salt minion in a subprocess.
    Auto restart minion on error.
    """
    import signal

    import salt.utils.platform
    import salt.utils.process

    salt.utils.process.notify_systemd()

    import salt.cli.daemons
    import multiprocessing

    # Fix for setuptools generated scripts, so that it will
    # work with multiprocessing fork emulation.
    # (see multiprocessing.forking.get_preparation_data())
    if __name__ != "__main__":
        sys.modules["__main__"] = sys.modules[__name__]

    if "" in sys.path:
        sys.path.remove("")

    if salt.utils.platform.is_windows():
        minion = salt.cli.daemons.Minion()
        minion.start()
        return
    # REMOVEME after Python 2.7 support is dropped (also the six import)
    elif six.PY2:
        from salt.utils.versions import warn_until

        # Message borrowed from pip's deprecation warning
        warn_until(
            "Sodium",
            "Python 2.7 will reach the end of its life on January 1st,"
            " 2020. Please upgrade your Python as Python 2.7 won't be"
            " maintained after that date.  Salt will drop support for"
            " Python 2.7 in the Sodium release or later.",
        )
    # END REMOVEME

    if "--disable-keepalive" in sys.argv:
        sys.argv.remove("--disable-keepalive")
        minion = salt.cli.daemons.Minion()
        minion.start()
        return

    def escalate_signal_to_process(
        pid, signum, sigframe
    ):  # pylint: disable=unused-argument
        """
        Escalate the signal received to the multiprocessing process that
        is actually running the minion
        """
        # escalate signal
        os.kill(pid, signum)

    # keep one minion subprocess running
    prev_sigint_handler = signal.getsignal(signal.SIGINT)
    prev_sigterm_handler = signal.getsignal(signal.SIGTERM)
    while True:
        try:
            process = multiprocessing.Process(target=minion_process)
            process.start()
            signal.signal(
                signal.SIGTERM,
                functools.partial(escalate_signal_to_process, process.pid),
            )
            signal.signal(
                signal.SIGINT,
                functools.partial(escalate_signal_to_process, process.pid),
            )
            signal.signal(
                signal.SIGHUP,
                functools.partial(escalate_signal_to_process, process.pid),
            )
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
    """
    Start a proxy minion process
    """
    import salt.cli.daemons
    import salt.utils.platform

    # salt_minion spawns this function in a new process

    lock = threading.RLock()

    def suicide_when_without_parent(parent_pid):
        """
        Have the minion suicide if the parent process is gone

        NOTE: there is a small race issue where the parent PID could be replace
        with another process with the same PID!
        """
        while lock.acquire(blocking=False):
            lock.release()
            time.sleep(5)
            try:
                # check pid alive (Unix only trick!)
                os.kill(parent_pid, 0)
            except OSError:
                # forcibly exit, regular sys.exit raises an exception-- which
                # isn't sufficient in a thread
                os._exit(999)

    try:
        if not salt.utils.platform.is_windows():
            thread = threading.Thread(
                target=suicide_when_without_parent, args=(os.getppid(),)
            )
            thread.start()

        restart = False
        proxyminion = None
        status = salt.defaults.exitcodes.EX_OK
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
        # pylint: disable=broad-except
    except (Exception, SaltClientError, SaltReqTimeoutError, SaltSystemExit,) as exc:
        # pylint: enable=broad-except
        log.error("Proxy Minion failed to start: ", exc_info=True)
        restart = True
        # status is superfluous since the process will be restarted
        status = salt.defaults.exitcodes.SALT_KEEPALIVE
    except SystemExit as exc:
        restart = False
        status = exc.code
    finally:
        lock.acquire(blocking=True)

    if restart is True:
        log.warning("** Restarting proxy minion **")
        delay = 60
        if proxyminion is not None:
            if hasattr(proxyminion, "config"):
                delay = proxyminion.config.get("random_reauth_delay", 60)
        random_delay = randint(1, delay)
        log.info("Sleeping random_reauth_delay of %s seconds", random_delay)
        # preform delay after minion resources have been cleaned
        queue.put(random_delay)
    else:
        queue.put(0)
    sys.exit(status)


def salt_proxy():
    """
    Start a proxy minion.
    """
    import salt.cli.daemons
    import salt.utils.platform
    import multiprocessing

    if "" in sys.path:
        sys.path.remove("")

    if salt.utils.platform.is_windows():
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
        return

    if "--disable-keepalive" in sys.argv:
        sys.argv.remove("--disable-keepalive")
        proxyminion = salt.cli.daemons.ProxyMinion()
        proxyminion.start()
        return

    # keep one minion subprocess running
    while True:
        try:
            queue = multiprocessing.Queue()
        except Exception:  # pylint: disable=broad-except
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
            except Exception:  # pylint: disable=broad-except
                if process.exitcode == 0:
                    # Minion process ended naturally, Ctrl+C or --version
                    break
                restart_delay = 60
            if restart_delay == 0:
                # Minion process ended naturally, Ctrl+C, --version, etc.
                sys.exit(process.exitcode)
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
    """
    Start the salt syndic.
    """
    import salt.utils.process

    salt.utils.process.notify_systemd()

    import salt.cli.daemons

    pid = os.getpid()
    try:
        syndic = salt.cli.daemons.Syndic()
        syndic.start()
    except KeyboardInterrupt:
        os.kill(pid, 15)


def salt_key():
    """
    Manage the authentication keys with salt-key.
    """
    import salt.cli.key

    try:
        client = salt.cli.key.SaltKey()
        _install_signal_handlers(client)
        client.run()
    except Exception as err:  # pylint: disable=broad-except
        sys.stderr.write("Error: {0}\n".format(err))


def salt_cp():
    """
    Publish commands to the salt system from the command line on the
    master.
    """
    import salt.cli.cp

    client = salt.cli.cp.SaltCPCli()
    _install_signal_handlers(client)
    client.run()


def salt_call():
    """
    Directly call a salt command in the modules, does not require a running
    salt minion to run.
    """
    import salt.cli.call

    if "" in sys.path:
        sys.path.remove("")
    client = salt.cli.call.SaltCall()
    _install_signal_handlers(client)
    client.run()


def salt_run():
    """
    Execute a salt convenience routine.
    """
    import salt.cli.run

    if "" in sys.path:
        sys.path.remove("")
    client = salt.cli.run.SaltRun()
    _install_signal_handlers(client)
    client.run()


def salt_ssh():
    """
    Execute the salt-ssh system
    """
    import salt.cli.ssh

    if "" in sys.path:
        sys.path.remove("")
    try:
        client = salt.cli.ssh.SaltSSH()
        _install_signal_handlers(client)
        client.run()
    except SaltClientError as err:
        trace = traceback.format_exc()
        try:
            hardcrash = client.options.hard_crash
        except (AttributeError, KeyError):
            hardcrash = False
        _handle_interrupt(SystemExit(err), err, hardcrash, trace=trace)


def salt_cloud():
    """
    The main function for salt-cloud
    """
    # Define 'salt' global so we may use it after ImportError. Otherwise,
    # UnboundLocalError will be raised.
    global salt  # pylint: disable=W0602

    try:
        # Late-imports for CLI performance
        import salt.cloud
        import salt.cloud.cli
    except ImportError as e:
        # No salt cloud on Windows
        log.error("Error importing salt cloud: %s", e)
        print("salt-cloud is not available in this system")
        sys.exit(salt.defaults.exitcodes.EX_UNAVAILABLE)
    if "" in sys.path:
        sys.path.remove("")

    client = salt.cloud.cli.SaltCloud()
    _install_signal_handlers(client)
    client.run()


def salt_api():
    """
    The main function for salt-api
    """
    import salt.utils.process

    salt.utils.process.notify_systemd()

    import salt.cli.api

    sapi = salt.cli.api.SaltAPI()  # pylint: disable=E1120
    sapi.start()


def salt_main():
    """
    Publish commands to the salt system from the command line on the
    master.
    """
    import salt.cli.salt

    if "" in sys.path:
        sys.path.remove("")
    client = salt.cli.salt.SaltCMD()
    _install_signal_handlers(client)
    client.run()


def salt_spm():
    """
    The main function for spm, the Salt Package Manager

    .. versionadded:: 2015.8.0
    """
    import salt.cli.spm

    spm = salt.cli.spm.SPM()  # pylint: disable=E1120
    spm.run()


def salt_extend(extension, name, description, salt_dir, merge):
    """
    Quickstart for developing on the saltstack installation

    .. versionadded:: 2016.11.0
    """
    import salt.utils.extend

    salt.utils.extend.run(
        extension=extension,
        name=name,
        description=description,
        salt_dir=salt_dir,
        merge=merge,
    )


def salt_unity():
    """
    Change the args and redirect to another salt script
    """
    avail = []
    for fun in dir(sys.modules[__name__]):
        if fun.startswith("salt"):
            avail.append(fun[5:])
    if len(sys.argv) < 2:
        msg = "Must pass in a salt command, available commands are:"
        for cmd in avail:
            msg += "\n{0}".format(cmd)
        print(msg)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd not in avail:
        # Fall back to the salt command
        sys.argv[0] = "salt"
        s_fun = salt_main
    else:
        sys.argv[0] = "salt-{0}".format(cmd)
        sys.argv.pop(1)
        s_fun = getattr(sys.modules[__name__], "salt_{0}".format(cmd))
    s_fun()
