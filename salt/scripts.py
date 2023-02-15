"""
This module contains the function calls to execute command line scripts
"""


import functools
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from random import randint

import salt.defaults.exitcodes
from salt.exceptions import SaltClientError, SaltReqTimeoutError, SaltSystemExit

log = logging.getLogger(__name__)

if sys.version_info < (3,):
    raise SystemExit(salt.defaults.exitcodes.EX_GENERIC)


def _handle_signals(client, signum, sigframe):
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

    if exit_msg is None and hardcrash:
        exit_msg = "\nExiting with hard crash on Ctrl-c"
    if exit_msg:
        print(exit_msg, file=sys.stderr, flush=True)
    if hardcrash:
        try:
            # This raises AttributeError on Python 3.4 and 3.5 if there is no current exception.
            # Ref: https://bugs.python.org/issue23003
            trace = traceback.format_exc()
            log.error(trace)
        except AttributeError:
            pass
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)
    sys.exit(salt.defaults.exitcodes.EX_OK)


def _install_signal_handlers(client):
    # Install the SIGINT/SIGTERM handlers if not done so far
    if signal.getsignal(signal.SIGINT) in (signal.SIG_DFL, signal.default_int_handler):
        # No custom signal handling was added, install our own
        signal.signal(signal.SIGINT, functools.partial(_handle_signals, client))

    if signal.getsignal(signal.SIGTERM) is signal.SIG_DFL:
        # No custom signal handling was added, install our own
        signal.signal(signal.SIGTERM, functools.partial(_handle_signals, client))


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

    master = salt.cli.daemons.Master()
    master.start()


def minion_process():
    """
    Start a minion process
    """
    # Because the minion is going to start on a separate process,
    # salt._logging.in_mainprocess() will return False.
    # We'll just force it to return True for this particular case so
    # that proper logging can be set up.
    import salt._logging

    salt._logging.in_mainprocess.__pid__ = os.getpid()
    # Now the remaining required imports
    import salt.cli.daemons
    import salt.utils.platform

    # salt_minion spawns this function in a new process

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

    import multiprocessing

    import salt.cli.daemons

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
            process = multiprocessing.Process(
                target=minion_process, name="MinionKeepAlive"
            )
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
    except (
        Exception,
        SaltClientError,
        SaltReqTimeoutError,
        SaltSystemExit,
    ) as exc:
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
    import multiprocessing

    import salt.cli.daemons
    import salt.utils.platform

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
        process = multiprocessing.Process(
            target=proxy_minion_process, args=(queue,), name="ProxyMinion"
        )
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
        sys.stderr.write("Error: {}\n".format(err))


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
        print(str(err), file=sys.stderr, flush=True)
        try:
            if client.options.hard_crash:
                trace = traceback.format_exc()
                log.error(trace)
        except (AttributeError, KeyError):
            pass
        sys.exit(salt.defaults.exitcodes.EX_GENERIC)


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
            msg += "\n{}".format(cmd)
        print(msg)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd not in avail:
        # Fall back to the salt command
        sys.argv[0] = "salt"
        s_fun = salt_main
    else:
        sys.argv[0] = "salt-{}".format(cmd)
        sys.argv.pop(1)
        s_fun = getattr(sys.modules[__name__], "salt_{}".format(cmd))
    s_fun()


def salt_pip():
    """
    Proxy to current python's pip
    """
    command = [
        sys.executable,
        "-m",
        "pip",
    ] + sys.argv[1:]
    ret = subprocess.run(command, shell=False, check=False)
    sys.exit(ret.returncode)
