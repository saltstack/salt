"""
tests.support.saltfactories_virt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module only exists to help with some  tests while the Salt code base
is not migrated to a newer salt-factories package
"""
# pylint: disable=resource-leakage

import atexit
import json
import logging
import os
import pathlib
import pprint
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime

import attr  # pylint: disable=3rd-party-module-not-gated
import msgpack
import psutil  # pylint: disable=3rd-party-module-not-gated
import pytest
import salt.config
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.path
import salt.utils.user
import salt.utils.verify
import salt.utils.yaml
import zmq
from salt.utils.immutabletypes import freeze
from saltfactories import CODE_ROOT_DIR
from saltfactories.exceptions import ProcessNotStarted as FactoryNotStarted
from saltfactories.exceptions import ProcessTimeout as FactoryTimeout
from saltfactories.utils import cli_scripts, ports, random_string
from saltfactories.utils.processes.bases import Popen, ProcessResult, ShellResult
from saltfactories.utils.processes.helpers import (
    terminate_process,
    terminate_process_list,
)
from tests.support.runtests import RUNTIME_VARS

try:
    import docker
    from docker.errors import APIError

    HAS_DOCKER = True
except ImportError:  # pragma: no cover
    HAS_DOCKER = False

    class APIError(Exception):
        pass


try:
    from requests.exceptions import ConnectionError as RequestsConnectionError

    HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    HAS_REQUESTS = False

    class RequestsConnectionError(ConnectionError):
        pass


try:
    import pywintypes

    PyWinTypesError = pywintypes.error
except ImportError:

    class PyWinTypesError(Exception):
        pass


try:
    from saltfactories.exceptions import (  # pylint: disable=no-name-in-module
        FactoryNotStarted,
    )

    raise RuntimeError("s0undt3ch, it's time to cleanup this spaghetti code!")
except ImportError:
    pass

log = logging.getLogger(__name__)


@attr.s(kw_only=True)
class Factory:
    """
    Base factory class

    Args:
        display_name(str):
            Human readable name for the factory
        environ(dict):
            A dictionary of `key`, `value` pairs to add to the environment.
        cwd (str):
            The path to the current working directory
    """

    display_name = attr.ib(default=None)
    cwd = attr.ib(default=None)
    environ = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        if self.environ is None:
            self.environ = os.environ.copy()
        if self.cwd is None:
            self.cwd = os.getcwd()

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name:
            return "{}({})".format(self.__class__.__name__, self.display_name)
        return self.__class__.__name__


@attr.s(kw_only=True)
class SubprocessFactoryBase(Factory):
    """
    Base CLI script/binary class

    Args:
        cli_script_name(str):
            This is the string containing the name of the binary to call on the subprocess, either the
            full path to it, or the basename. In case of the basename, the directory containing the
            basename must be in your ``$PATH`` variable.
        base_script_args(list or tuple):
            An list or tuple iterable of the base arguments to use when building the command line to
            launch the process
        slow_stop(bool):
            Whether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
            :py:meth:`~subprocess.Popen.terminate` on the sub-process.
            When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
            can be written down to disk.
    """

    cli_script_name = attr.ib()
    base_script_args = attr.ib(default=None)
    slow_stop = attr.ib(default=True)

    _terminal = attr.ib(repr=False, init=False, default=None)
    _terminal_result = attr.ib(repr=False, init=False, default=None)
    _terminal_timeout = attr.ib(repr=False, init=False, default=None)
    _children = attr.ib(repr=False, init=False, default=attr.Factory(list))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.base_script_args is None:
            self.base_script_args = []

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        return self.display_name or self.cli_script_name

    def get_script_path(self):
        """
        Returns the path to the script to run
        """
        if os.path.isabs(self.cli_script_name):
            script_path = self.cli_script_name
        else:
            script_path = salt.utils.path.which(self.cli_script_name)
        if not script_path or not os.path.exists(script_path):
            pytest.fail("The CLI script {!r} does not exist".format(script_path))
        return script_path

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return list(self.base_script_args)

    def get_script_args(self):  # pylint: disable=no-self-use
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def build_cmdline(self, *args):
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
        """
        return (
            [self.get_script_path()]
            + self.get_base_script_args()
            + self.get_script_args()
            + list(args)
        )

    def init_terminal(self, cmdline, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionally, it sets a reference to it in self._terminal and also collects
        an initial listing of child processes which will be used when terminating the
        terminal
        """
        self._terminal = Popen(cmdline, **kwargs)
        # Reset the previous _terminal_result if set
        self._terminal_result = None
        # A little sleep to allow the subprocess to start
        time.sleep(0.125)
        try:
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)
        except psutil.NoSuchProcess:
            # The terminal process is gone
            pass
        atexit.register(self.terminate)
        return self._terminal

    def is_running(self):
        """
        Returns true if the sub-process is alive
        """
        if not self._terminal:
            return False
        return self._terminal.poll() is None

    def terminate(self):
        """
        Terminate the started daemon
        """
        if self._terminal is None:
            return self._terminal_result
        atexit.unregister(self.terminate)
        log.info("Stopping %s", self)
        # Collect any child processes information before terminating the process
        try:
            for child in psutil.Process(self._terminal.pid).children(recursive=True):
                if child not in self._children:
                    self._children.append(child)
        except psutil.NoSuchProcess:
            # The terminal process is gone
            pass

        # poll the terminal before trying to terminate it, running or not, so that
        # the right returncode is set on the popen object
        self._terminal.poll()
        # Lets log and kill any child processes left behind
        terminate_process(
            pid=self._terminal.pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.slow_stop,
        )
        stdout, stderr = self._terminal.communicate()
        try:
            log_message = "Terminated {}.".format(self)
            if stdout or stderr:
                log_message += " Process Output:"
                if stdout:
                    log_message += "\n>>>>> STDOUT >>>>>\n{}\n<<<<< STDOUT <<<<<".format(
                        stdout.strip()
                    )
                if stderr:
                    log_message += "\n>>>>> STDERR >>>>>\n{}\n<<<<< STDERR <<<<<".format(
                        stderr.strip()
                    )
                log_message += "\n"
            log.info(log_message)
            self._terminal_result = ProcessResult(
                self._terminal.returncode, stdout, stderr, cmdline=self._terminal.args
            )
            return self._terminal_result
        finally:
            self._terminal = None
            self._terminal_timeout = None
            self._children = []

    @property
    def pid(self):
        if not self._terminal:
            return
        return self._terminal.pid

    def _run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        cmdline = self.build_cmdline(*args, **kwargs)

        log.info("%s is running %r in CWD: %s ...", self, cmdline, self.cwd)

        terminal = self.init_terminal(cmdline, cwd=self.cwd, env=self.environ)
        try:
            self._children.extend(psutil.Process(self.pid).children(recursive=True))
        except psutil.NoSuchProcess:
            # Process already died?!
            pass
        return terminal


@attr.s(kw_only=True)
class ProcessFactory(SubprocessFactoryBase):
    """
    Base process factory

    Args:
        default_timeout(int):
            The maximum amount of seconds that a script should run
    """

    default_timeout = attr.ib()
    _terminal_timeout_set_explicitly = attr.ib(repr=False, init=False, default=False)

    @default_timeout.default
    def _set_default_timeout(self):
        if not sys.platform.startswith(("win", "darwin")):
            return 30
        # Windows and macOS are just slower.
        return 120

    def run(self, *args, _timeout=None, **kwargs):
        """
        Run the given command synchronously
        """
        start_time = time.time()
        # Build the cmdline to pass to the terminal
        # We set the _terminal_timeout attribute while calling build_cmdline in case it needs
        # access to that information to build the command line
        self._terminal_timeout = _timeout or self.default_timeout
        self._terminal_timeout_set_explicitly = _timeout is not None
        timeout_expire = time.time() + self._terminal_timeout
        running = self._run(*args, **kwargs)

        timmed_out = False
        while True:
            if timeout_expire < time.time():
                timmed_out = True
                break
            if self._terminal.poll() is not None:
                break
            time.sleep(0.25)

        result = self.terminate()
        if timmed_out:
            raise FactoryTimeout(
                "{} Failed to run: {}; Error: Timed out after {:.2f} seconds!".format(
                    self, result.cmdline, time.time() - start_time
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                cmdline=result.cmdline,
                exitcode=result.exitcode,
            )

        cmdline = result.cmdline
        exitcode = result.exitcode
        stdout, stderr, json_out = self.process_output(
            result.stdout, result.stderr, cmdline=cmdline
        )
        log.info(
            "%s completed %r in CWD: %s after %.2f seconds",
            self,
            cmdline,
            self.cwd,
            time.time() - start_time,
        )
        return ShellResult(exitcode, stdout, stderr, json=json_out, cmdline=cmdline)

    def process_output(self, stdout, stderr, cmdline=None):
        if stdout:
            try:
                json_out = json.loads(stdout)
            except ValueError:
                log.debug(
                    "%s failed to load JSON from the following output:\n%r",
                    self,
                    stdout,
                )
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class DaemonFactory(SubprocessFactoryBase):
    """
    Base daemon factory
    """

    check_ports = attr.ib(default=None)
    factories_manager = attr.ib(repr=False, hash=False, default=None)
    start_timeout = attr.ib(repr=False)
    max_start_attempts = attr.ib(repr=False, default=3)
    before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    before_terminate_callbacks = attr.ib(
        repr=False, hash=False, default=attr.Factory(list)
    )
    after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_terminate_callbacks = attr.ib(
        repr=False, hash=False, default=attr.Factory(list)
    )
    extra_cli_arguments_after_first_start_failure = attr.ib(
        hash=False, default=attr.Factory(list)
    )
    listen_ports = attr.ib(
        init=False, repr=False, hash=False, default=attr.Factory(list)
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.check_ports and not isinstance(self.check_ports, (list, tuple)):
            self.check_ports = [self.check_ports]
        if self.check_ports:
            self.listen_ports.extend(self.check_ports)
        self.register_after_start_callback(self._add_factory_to_stats_processes)
        self.register_after_terminate_callback(
            self._terminate_processes_matching_listen_ports
        )
        self.register_after_terminate_callback(
            self._remove_factory_from_stats_processes
        )

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.after_terminate_callbacks.append((callback, args, kwargs))

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join([repr(arg) for arg in args])
        if kwargs:
            callback_str += ", ".join(
                ["{}={!r}".format(k, v) for (k, v) in kwargs.items()]
            )
        callback_str += ")"
        return callback_str

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        """
        Start the daemon
        """
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        process_running = False
        start_time = time.time()
        start_attempts = max_start_attempts or self.max_start_attempts
        current_attempt = 0
        run_arguments = list(extra_cli_arguments)
        while True:
            if process_running:
                break
            current_attempt += 1
            if current_attempt > start_attempts:
                break
            log.info(
                "Starting %s. Attempt: %d of %d", self, current_attempt, start_attempts
            )
            for callback, args, kwargs in self.before_start_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
            current_start_time = time.time()
            start_running_timeout = current_start_time + (
                start_timeout or self.start_timeout
            )
            if (
                current_attempt > 1
                and self.extra_cli_arguments_after_first_start_failure
            ):
                run_arguments = list(extra_cli_arguments) + list(
                    self.extra_cli_arguments_after_first_start_failure
                )
            self._run(*run_arguments)
            if not self.is_running():
                # A little breathe time to allow the process to start if not started already
                time.sleep(0.5)
            while time.time() <= start_running_timeout:
                if not self.is_running():
                    log.warning("%s is no longer running", self)
                    self.terminate()
                    break
                try:
                    if (
                        self.run_start_checks(current_start_time, start_running_timeout)
                        is False
                    ):
                        time.sleep(1)
                        continue
                except FactoryNotStarted:
                    self.terminate()
                    break
                log.info(
                    "The %s factory is running after %d attempts. Took %1.2f seconds",
                    self,
                    current_attempt,
                    time.time() - start_time,
                )
                process_running = True
                break
            else:
                # The factory failed to confirm it's running status
                self.terminate()
        if process_running:
            for callback, args, kwargs in self.after_start_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
            return process_running
        result = self.terminate()
        raise FactoryNotStarted(
            "The {} factory has failed to confirm running status after {} attempts, which "
            "took {:.2f} seconds".format(
                self, current_attempt - 1, time.time() - start_time,
            ),
            stdout=result.stdout,
            stderr=result.stderr,
            exitcode=result.exitcode,
        )

    def started(
        self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None
    ):
        """
        Start the daemon and return it's instance so it can be used as a context manager
        """
        self.start(
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout
        )
        return self

    def terminate(self):
        if self._terminal_result is not None:
            # This factory has already been terminated
            return self._terminal_result
        for callback, args, kwargs in self.before_terminate_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    self._format_callback(callback, args, kwargs),
                    exc,
                    exc_info=True,
                )
        try:
            return super().terminate()
        finally:
            for callback, args, kwargs in self.after_terminate_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )

    def run_start_checks(self, started_at, timeout_at):
        check_ports = set(self.get_check_ports())
        if not check_ports:
            log.debug("No ports to check connection to for %s", self)
            return True
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
            if check_ports:
                time.sleep(0.5)
        else:
            log.error(
                "Failed to check ports after %1.2f seconds for %s",
                time.time() - checks_start_time,
                self,
            )
            return False
        log.debug(
            "Successfuly connected to all ports(%s) for %s",
            set(self.get_check_ports()),
            self,
        )
        return True

    def _add_factory_to_stats_processes(self):
        if (
            self.factories_manager
            and self.factories_manager.stats_processes is not None
        ):
            display_name = self.get_display_name()
            self.factories_manager.stats_processes[display_name] = psutil.Process(
                self.pid
            )

    def _remove_factory_from_stats_processes(self):
        if (
            self.factories_manager
            and self.factories_manager.stats_processes is not None
        ):
            display_name = self.get_display_name()
            self.factories_manager.stats_processes.pop(display_name, None)

    def _terminate_processes_matching_listen_ports(self):
        if not self.listen_ports:
            return
        # If any processes were not terminated and are listening on the ports
        # we have set on listen_ports, terminate those processes.
        found_processes = []
        for process in psutil.process_iter(["connections"]):
            try:
                for connection in process.connections():
                    if connection.status != psutil.CONN_LISTEN:
                        # We only care about listening services
                        continue
                    if connection.laddr.port in self.check_ports:
                        found_processes.append(process)
                        # We already found one connection, no need to check the others
                        break
            except psutil.AccessDenied:
                # We've been denied access to this process connections. Carry on.
                continue
        if found_processes:
            log.debug(
                "The following processes were found listening on ports %s: %s",
                ", ".join([str(port) for port in self.listen_ports]),
                found_processes,
            )
            terminate_process_list(found_processes, kill=True, slow_stop=False)
        else:
            log.debug(
                "No astray processes were found listening on ports: %s",
                ", ".join([str(port) for port in self.listen_ports]),
            )

    def __enter__(self):
        if not self.is_running():
            raise RuntimeError(
                "Factory not yet started. Perhaps you're after something like:\n\n"
                "with {}.started() as factory:\n"
                "    yield factory".format(self.__class__.__name__)
            )
        return self

    def __exit__(self, *exc):
        return self.terminate()


@attr.s(kw_only=True)
class SaltFactory:
    """
    Base factory for salt cli's and daemon's

    Args:
        config(dict):
            The Salt config dictionary
        python_executable(str):
            The path to the python executable to use
    """

    id = attr.ib(default=None, init=False)
    config = attr.ib(repr=False)
    config_dir = attr.ib(init=False, default=None)
    config_file = attr.ib(init=False, default=None)
    python_executable = attr.ib(default=None)
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        if self.python_executable is None:
            self.python_executable = sys.executable
        # We really do not want buffered output
        self.environ.setdefault("PYTHONUNBUFFERED", "1")
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        self.config_file = self.config["conf_file"]
        self.config_dir = os.path.dirname(self.config_file)
        self.id = self.config["id"]
        self.config = freeze(self.config)

    def get_display_name(self):
        """
        Returns a human readable name for the factory
        """
        if self.display_name is None:
            self.display_name = "{}(id={!r})".format(self.__class__.__name__, self.id)
        return super().get_display_name()


@attr.s(kw_only=True)
class SaltCliFactory(SaltFactory, ProcessFactory):
    """
    Base factory for salt cli's

    Args:
        hard_crash(bool):
            Pass ``--hard-crash`` to Salt's CLI's
    """

    hard_crash = attr.ib(repr=False, default=False)
    # Override the following to default to non-mandatory and to None
    display_name = attr.ib(init=False, default=None)
    _minion_tgt = attr.ib(repr=False, init=False, default=None)

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=False)
    __cli_log_level_supported__ = attr.ib(repr=False, init=False, default=True)
    __cli_output_supported__ = attr.ib(repr=False, init=False, default=True)
    # Override the following to default to non-mandatory and to None
    display_name = attr.ib(init=False, default=None)

    def __attrs_post_init__(self):
        ProcessFactory.__attrs_post_init__(self)
        SaltFactory.__attrs_post_init__(self)

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if not self.hard_crash:
            return super().get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, minion_tgt=None):
        return minion_tgt

    def build_cmdline(
        self, *args, minion_tgt=None, **kwargs
    ):  # pylint: disable=arguments-differ
        """
        Construct a list of arguments to use when starting the subprocess

        Args:
            args:
                Additional arguments to use when starting the subprocess
            kwargs:
                Keyword arguments will be converted into ``key=value`` pairs to be consumed by the salt CLI's
            minion_tgt(str):
                The minion ID to target
        """
        log.debug(
            "Building cmdline. Minion target: %s; Input args: %s; Input kwargs: %s;",
            minion_tgt,
            args,
            kwargs,
        )
        minion_tgt = self._minion_tgt = self.get_minion_tgt(minion_tgt=minion_tgt)
        cmdline = []

        args = list(args)

        # Handle the config directory flag
        for arg in args:
            if arg.startswith("--config-dir="):
                break
            if arg in ("-c", "--config-dir"):
                break
        else:
            cmdline.append("--config-dir={}".format(self.config_dir))

        # Handle the timeout CLI flag, if supported
        if self.__cli_timeout_supported__:
            salt_cli_timeout_next = False
            for arg in args:
                if arg.startswith("--timeout="):
                    # Let's actually change the _terminal_timeout value which is used to
                    # calculate when the run() method should actually timeout
                    if self._terminal_timeout_set_explicitly is False:
                        salt_cli_timeout = arg.split("--timeout=")[-1]
                        try:
                            self._terminal_timeout = int(salt_cli_timeout) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if salt_cli_timeout_next:
                    if self._terminal_timeout_set_explicitly is False:
                        try:
                            self._terminal_timeout = int(arg) + 5
                        except ValueError:
                            # Not a number? Let salt do it's error handling
                            pass
                    break
                if arg == "-t" or arg.startswith("--timeout"):
                    salt_cli_timeout_next = True
                    continue
            else:
                salt_cli_timeout = self._terminal_timeout
                if salt_cli_timeout and self._terminal_timeout_set_explicitly is False:
                    # Shave off a few seconds so that the salt command times out before the terminal does
                    salt_cli_timeout -= 5
                if salt_cli_timeout:
                    # If it's still a positive number, add it to the salt command CLI flags
                    cmdline.append("--timeout={}".format(salt_cli_timeout))

        # Handle the output flag
        if self.__cli_output_supported__:
            for arg in args:
                if arg in ("--out", "--output"):
                    break
                if arg.startswith(("--out=", "--output=")):
                    break
            else:
                # No output was passed, the default output is JSON
                cmdline.append("--out=json")

        if self.__cli_log_level_supported__:
            # Handle the logging flag
            for arg in args:
                if arg in ("-l", "--log-level"):
                    break
                if arg.startswith("--log-level="):
                    break
            else:
                # Default to being quiet on console output
                cmdline.append("--log-level=quiet")

        if minion_tgt:
            cmdline.append(minion_tgt)

        # Add the remaining args
        cmdline.extend(args)

        # Keyword arguments get passed as KEY=VALUE pairs to the CLI
        for key in kwargs:
            value = kwargs[key]
            if not isinstance(value, str):
                value = json.dumps(value)
            cmdline.append("{}={}".format(key, value))
        cmdline = super().build_cmdline(*cmdline)
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        log.debug("Built cmdline: %s", cmdline)
        return cmdline

    def process_output(self, stdout, stderr, cmdline=None):
        stdout, stderr, json_out = super().process_output(
            stdout, stderr, cmdline=cmdline
        )
        if (
            self.__cli_output_supported__
            and json_out
            and isinstance(json_out, str)
            and "--out=json" in cmdline
        ):
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        if self.__cli_output_supported__ and json_out and self._minion_tgt:
            try:
                json_out = json_out[self._minion_tgt]
            except KeyError:
                pass
        return stdout, stderr, json_out


@attr.s(kw_only=True)
class SaltDaemonFactory(SaltFactory, DaemonFactory):
    """
    Base factory for salt daemon's
    """

    display_name = attr.ib(init=False, default=None)
    event_listener = attr.ib(repr=False, default=None)
    started_at = attr.ib(repr=False, default=None)

    def __attrs_post_init__(self):
        DaemonFactory.__attrs_post_init__(self)
        SaltFactory.__attrs_post_init__(self)
        for arg in self.extra_cli_arguments_after_first_start_failure:
            if arg in ("-l", "--log-level"):
                break
            if arg.startswith("--log-level="):
                break
        else:
            self.extra_cli_arguments_after_first_start_failure.append(
                "--log-level=debug"
            )

    @classmethod
    def configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        **configure_kwargs
    ):
        return cls._configure(
            factories_manager,
            daemon_id,
            root_dir=root_dir,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            **configure_kwargs
        )

    @classmethod
    def _configure(
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
    ):
        raise NotImplementedError

    @classmethod
    def verify_config(cls, config):
        salt.utils.verify.verify_env(
            cls._get_verify_config_entries(config),
            salt.utils.user.get_user(),
            pki_dir=config.get("pki_dir") or "",
            root_dir=config["root_dir"],
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        raise NotImplementedError

    @classmethod
    def write_config(cls, config):
        config_file = config.pop("conf_file")
        log.debug(
            "Writing to configuration file %s. Configuration:\n%s",
            config_file,
            pprint.pformat(config),
        )

        # Write down the computed configuration into the config file
        with salt.utils.files.fopen(config_file, "w") as wfh:
            salt.utils.yaml.safe_dump(config, wfh, default_flow_style=False)
        loaded_config = cls.load_config(config_file, config)
        cls.verify_config(loaded_config)
        return loaded_config

    @classmethod
    def load_config(cls, config_file, config):
        """
        Should return the configuration as the daemon would have loaded after
        parsing the CLI
        """
        raise NotImplementedError

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError

    def run_start_checks(self, started_at, timeout_at):
        if not super().run_start_checks(started_at, timeout_at):
            return False
        if not self.event_listener:
            log.debug(
                "The 'event_listener' attribute is not set. Not checking events..."
            )
            return True

        check_events = set(self.get_check_events())
        if not check_events:
            log.debug("No events to listen to for %s", self)
            return True
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_events:
                break
            check_events -= self.event_listener.get_events(
                check_events, after_time=started_at
            )
            if check_events:
                time.sleep(0.5)
        else:
            log.error(
                "Failed to check events after %1.2f seconds for %s",
                time.time() - checks_start_time,
                self,
            )
            return False
        log.debug(
            "Successfuly checked for all events(%s) for %s",
            set(self.get_check_events()),
            self,
        )
        return True

    def build_cmdline(self, *args):
        _args = []
        # Handle the config directory flag
        for arg in args:
            if arg.startswith("--config-dir="):
                break
            if arg in ("-c", "--config-dir"):
                break
        else:
            _args.append("--config-dir={}".format(self.config_dir))
        # Handle the logging flag
        for arg in args:
            if arg in ("-l", "--log-level"):
                break
            if arg.startswith("--log-level="):
                break
        else:
            # Default to being quiet on console output
            _args.append("--log-level=quiet")
        cmdline = super().build_cmdline(*(_args + list(args)))
        if self.python_executable:
            if cmdline[0] != self.python_executable:
                cmdline.insert(0, self.python_executable)
        return cmdline


@attr.s(kw_only=True, slots=True)
class SaltCallCliFactory(SaltCliFactory):
    """
    salt-call CLI factory
    """

    __cli_timeout_supported__ = attr.ib(repr=False, init=False, default=True)

    def get_minion_tgt(self, minion_tgt=None):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # Under salt-call, the minion target is always "local"
        self._minion_tgt = "local"
        return super().process_output(stdout, stderr, cmdline=cmdline)


@attr.s(kw_only=True, slots=True)
class SaltMinionFactory(SaltDaemonFactory):
    @classmethod
    def default_config(
        cls,
        root_dir,
        minion_id,
        config_defaults=None,
        config_overrides=None,
        master=None,
    ):
        if config_defaults is None:
            config_defaults = {}

        master_id = master_port = None
        if master is not None:
            master_id = master.id
            master_port = master.config["ret_port"]
            # Match transport if not set
            config_defaults.setdefault("transport", master.config["transport"])

        conf_dir = root_dir / "conf"
        conf_dir.mkdir(parents=True, exist_ok=True)
        conf_file = str(conf_dir / "minion")

        _config_defaults = {
            "id": minion_id,
            "conf_file": conf_file,
            "root_dir": str(root_dir),
            "interface": "127.0.0.1",
            "master": "127.0.0.1",
            "master_port": master_port or ports.get_unused_localhost_port(),
            "tcp_pub_port": ports.get_unused_localhost_port(),
            "tcp_pull_port": ports.get_unused_localhost_port(),
            "pidfile": "run/minion.pid",
            "pki_dir": "pki",
            "cachedir": "cache",
            "sock_dir": "run/minion",
            "log_file": "logs/minion.log",
            "log_level_logfile": "debug",
            "loop_interval": 0.05,
            "log_fmt_console": "%(asctime)s,%(msecs)03.0f [%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "log_fmt_logfile": "[%(asctime)s,%(msecs)03.0f][%(name)-17s:%(lineno)-4d][%(levelname)-8s][%(processName)18s(%(process)d)] %(message)s",
            "pytest-minion": {
                "master-id": master_id,
                "log": {"prefix": "{}(id={!r})".format(cls.__name__, minion_id)},
            },
            "acceptance_wait_time": 0.5,
            "acceptance_wait_time_max": 5,
        }
        # Merge in the initial default options with the internal _config_defaults
        salt.utils.dictupdate.update(
            config_defaults, _config_defaults, merge_lists=True
        )

        if config_overrides:
            # Merge in the default options with the minion_config_overrides
            salt.utils.dictupdate.update(
                config_defaults, config_overrides, merge_lists=True
            )

        return config_defaults

    @classmethod
    def _configure(  # pylint: disable=arguments-differ
        cls,
        factories_manager,
        daemon_id,
        root_dir=None,
        config_defaults=None,
        config_overrides=None,
        master=None,
    ):
        return cls.default_config(
            root_dir,
            daemon_id,
            config_defaults=config_defaults,
            config_overrides=config_overrides,
            master=master,
        )

    @classmethod
    def _get_verify_config_entries(cls, config):
        # verify env to make sure all required directories are created and have the
        # right permissions
        pki_dir = pathlib.Path(config["pki_dir"])
        return [
            str(pki_dir / "minions"),
            str(pki_dir / "minions_pre"),
            str(pki_dir / "minions_rejected"),
            str(pki_dir / "accepted"),
            str(pki_dir / "rejected"),
            str(pki_dir / "pending"),
            str(pathlib.Path(config["log_file"]).parent),
            str(pathlib.Path(config["cachedir"]) / "proc"),
            # config['extension_modules'],
            config["sock_dir"],
        ]

    @classmethod
    def load_config(cls, config_file, config):
        return salt.config.minion_config(
            config_file, minion_id=config["id"], cache_minion_id=True
        )

    def get_script_args(self):
        args = super().get_script_args()
        if sys.platform.startswith("win") is False:
            args.append("--disable-keepalive")
        return args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        if not pytest_config.get("master-id"):
            log.warning(
                "Will not be able to check for start events for %s since it's missing the 'master-id' key "
                "in the 'pytest-%s' dictionary, or it's value is None.",
                self,
                self.config["__role"],
            )
        else:
            yield pytest_config["master-id"], "salt/{role}/{id}/start".format(
                role=self.config["__role"], id=self.id
            )

    def get_salt_call_cli(
        self, factory_class=SaltCallCliFactory, **factory_class_kwargs
    ):
        """
        Return a `salt-call` CLI process for this minion instance
        """
        script_path = cli_scripts.generate_script(
            self.factories_manager.scripts_dir,
            "salt-call",
            code_dir=self.factories_manager.code_dir,
            inject_coverage=self.factories_manager.inject_coverage,
            inject_sitecustomize=self.factories_manager.inject_sitecustomize,
        )
        return factory_class(
            cli_script_name=script_path,
            config=self.config.copy(),
            **factory_class_kwargs
        )


@attr.s(kw_only=True)
class ContainerFactory(Factory):
    image = attr.ib()
    name = attr.ib(default=None)
    check_ports = attr.ib(default=None)
    docker_client = attr.ib(repr=False, default=None)
    container_run_kwargs = attr.ib(repr=False, default=attr.Factory(dict))
    container = attr.ib(init=False, default=None, repr=False)
    start_timeout = attr.ib(repr=False, default=30)
    max_start_attempts = attr.ib(repr=False, default=3)
    before_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    before_terminate_callbacks = attr.ib(
        repr=False, hash=False, default=attr.Factory(list)
    )
    after_start_callbacks = attr.ib(repr=False, hash=False, default=attr.Factory(list))
    after_terminate_callbacks = attr.ib(
        repr=False, hash=False, default=attr.Factory(list)
    )
    _terminate_result = attr.ib(repr=False, hash=False, init=False, default=None)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.name is None:
            self.name = random_string("factories-")
        if self.docker_client is None:
            if not HAS_DOCKER:
                raise RuntimeError("The docker python library was not found installed")
            if not HAS_REQUESTS:
                raise RuntimeError(
                    "The requests python library was not found installed"
                )
            self.docker_client = docker.from_env()

    def _format_callback(self, callback, args, kwargs):
        callback_str = "{}(".format(callback.__name__)
        if args:
            callback_str += ", ".join(args)
        if kwargs:
            callback_str += ", ".join(
                ["{}={!r}".format(k, v) for (k, v) in kwargs.items()]
            )
        callback_str += ")"
        return callback_str

    def register_before_start_callback(self, callback, *args, **kwargs):
        self.before_start_callbacks.append((callback, args, kwargs))

    def register_before_terminate_callback(self, callback, *args, **kwargs):
        self.before_terminate_callbacks.append((callback, args, kwargs))

    def register_after_start_callback(self, callback, *args, **kwargs):
        self.after_start_callbacks.append((callback, args, kwargs))

    def register_after_terminate_callback(self, callback, *args, **kwargs):
        self.after_terminate_callbacks.append((callback, args, kwargs))

    def start(self, *command, max_start_attempts=None, start_timeout=None):
        if self.is_running():
            log.warning("%s is already running.", self)
            return True
        connectable = ContainerFactory.client_connectable(self.docker_client)
        if connectable is not True:
            self.terminate()
            raise RuntimeError(connectable)
        self._terminate_result = None
        atexit.register(self.terminate)
        factory_started = False
        for callback, args, kwargs in self.before_start_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    self._format_callback(callback, args, kwargs),
                    exc,
                    exc_info=True,
                )

        start_time = time.time()
        start_attempts = max_start_attempts or self.max_start_attempts
        current_attempt = 0
        while current_attempt <= start_attempts:
            current_attempt += 1
            if factory_started:
                break
            log.info(
                "Starting %s. Attempt: %d of %d", self, current_attempt, start_attempts
            )
            current_start_time = time.time()
            start_running_timeout = current_start_time + (
                start_timeout or self.start_timeout
            )

            # Start the container
            self.container = self.docker_client.containers.run(
                self.image,
                name=self.name,
                detach=True,
                stdin_open=True,
                command=list(command) or None,
                **self.container_run_kwargs
            )
            while time.time() <= start_running_timeout:
                # Don't know why, but if self.container wasn't previously in a running
                # state, and now it is, we have to re-set the self.container attribute
                # so that it gives valid status information
                self.container = self.docker_client.containers.get(self.name)
                if self.container.status != "running":
                    time.sleep(0.25)
                    continue

                self.container = self.docker_client.containers.get(self.name)
                logs = self.container.logs(stdout=True, stderr=True, stream=False)
                if isinstance(logs, bytes):
                    stdout = logs.decode()
                    stderr = None
                else:
                    stdout = logs[0].decode()
                    stderr = logs[1].decode()
                log.warning("Running Container Logs:\n%s\n%s", stdout, stderr)

                # If we reached this far it means that we got the running status above, and
                # now that the container has started, run start checks
                try:
                    if (
                        self.run_container_start_checks(
                            current_start_time, start_running_timeout
                        )
                        is False
                    ):
                        time.sleep(0.5)
                        continue
                except FactoryNotStarted:
                    self.terminate()
                    break
                log.info(
                    "The %s factory is running after %d attempts. Took %1.2f seconds",
                    self,
                    current_attempt,
                    time.time() - start_time,
                )
                factory_started = True
                break
            else:
                # We reached start_running_timeout, re-try
                try:
                    self.container.remove(force=True)
                    self.container.wait()
                except docker.errors.NotFound:
                    pass
                self.container = None
        else:
            # The factory failed to confirm it's running status
            self.terminate()
        if factory_started:
            for callback, args, kwargs in self.after_start_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
            # TODO: Add containers to the processes stats?!
            # if self.factories_manager and self.factories_manager.stats_processes is not None:
            #    self.factories_manager.stats_processes[self.get_display_name()] = psutil.Process(
            #        self.pid
            #    )
            return factory_started
        result = self.terminate()
        raise FactoryNotStarted(
            "The {} factory has failed to confirm running status after {} attempts, which "
            "took {:.2f} seconds({:.2f} seconds each)".format(
                self,
                current_attempt - 1,
                time.time() - start_time,
                start_timeout or self.start_timeout,
            ),
            stdout=result.stdout,
            stderr=result.stderr,
            exitcode=result.exitcode,
        )

    def started(self, *command, max_start_attempts=None, start_timeout=None):
        """
        Start the container and return it's instance so it can be used as a context manager
        """
        self.start(
            *command, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        return self

    def terminate(self):
        if self._terminate_result is not None:
            # The factory is already terminated
            return self._terminate_result
        atexit.unregister(self.terminate)
        for callback, args, kwargs in self.before_terminate_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                log.info(
                    "Exception raised when running %s: %s",
                    self._format_callback(callback, args, kwargs),
                    exc,
                    exc_info=True,
                )
        stdout = stderr = None
        try:
            if self.container is not None:
                container = self.docker_client.containers.get(self.name)
                logs = container.logs(stdout=True, stderr=True, stream=False)
                if isinstance(logs, bytes):
                    stdout = logs.decode()
                else:
                    stdout = logs[0].decode()
                    stderr = logs[1].decode()
                log.warning("Stopped Container Logs:\n%s\n%s", stdout, stderr)
                if container.status == "running":
                    container.remove(force=True)
                    container.wait()
                self.container = None
        except docker.errors.NotFound:
            pass
        finally:
            for callback, args, kwargs in self.after_terminate_callbacks:
                try:
                    callback(*args, **kwargs)
                except Exception as exc:  # pylint: disable=broad-except
                    log.info(
                        "Exception raised when running %s: %s",
                        self._format_callback(callback, args, kwargs),
                        exc,
                        exc_info=True,
                    )
        self._terminate_result = ProcessResult(exitcode=0, stdout=stdout, stderr=stderr)
        return self._terminate_result

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return self.check_ports or []

    def is_running(self):
        if self.container is None:
            log.warning("self.container is None")
            return False

        self.container = self.docker_client.containers.get(self.name)
        return self.container.status == "running"

    def run(self, *cmd, **kwargs):
        if len(cmd) == 1:
            cmd = cmd[0]
        log.info("%s is running %r ...", self, cmd)
        # We force dmux to True so that we always get back both stdout and stderr
        container = self.docker_client.containers.get(self.name)
        ret = container.exec_run(cmd, demux=True, **kwargs)
        exitcode = ret.exit_code
        stdout = stderr = None
        if ret.output:
            stdout, stderr = ret.output
        if stdout is not None:
            stdout = stdout.decode()
        if stderr is not None:
            stderr = stderr.decode()
        return ProcessResult(
            exitcode=exitcode, stdout=stdout, stderr=stderr, cmdline=cmd
        )

    @staticmethod
    def client_connectable(docker_client):
        try:
            if not docker_client.ping():
                return "The docker client failed to get a ping response from the docker daemon"
            return True
        except (APIError, RequestsConnectionError, PyWinTypesError) as exc:
            return "The docker client failed to ping the docker server: {}".format(exc)

    def run_container_start_checks(self, started_at, timeout_at):
        checks_start_time = time.time()
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if self._container_start_checks():
                break
        else:
            log.error(
                "Failed to run container start checks after %1.2f seconds",
                time.time() - checks_start_time,
            )
            return False
        check_ports = set(self.get_check_ports())
        if not check_ports:
            return True
        while time.time() <= timeout_at:
            if not self.is_running():
                raise FactoryNotStarted("{} is no longer running".format(self))
            if not check_ports:
                break
            check_ports -= ports.get_connectable_ports(check_ports)
            if check_ports:
                time.sleep(0.5)
        else:
            log.error(
                "Failed to check ports after %1.2f seconds",
                time.time() - checks_start_time,
            )
            return False
        return True

    def _container_start_checks(self):
        return True

    def __enter__(self):
        if not self.is_running():
            raise RuntimeError(
                "Factory not yet started. Perhaps you're after something like:\n\n"
                "with {}.started() as factory:\n"
                "    yield factory".format(self.__class__.__name__)
            )
        return self

    def __exit__(self, *exc):
        return self.terminate()


@attr.s(kw_only=True)
class SaltDaemonContainerFactory(SaltDaemonFactory, ContainerFactory):
    def __attrs_post_init__(self):
        self.daemon_started = self.daemon_starting = False
        if self.python_executable is None:
            # Default to whatever is the default python in the container
            self.python_executable = "python"
        SaltDaemonFactory.__attrs_post_init__(self)
        ContainerFactory.__attrs_post_init__(self)
        # There are some volumes which NEED to exist on the container so
        # that configs are in the right place and also our custom salt
        # plugins along with the custom scripts to start the daemons.
        root_dir = os.path.dirname(self.config["root_dir"])
        config_dir = str(self.config_dir)
        scripts_dir = str(self.factories_manager.scripts_dir)
        volumes = {
            root_dir: {"bind": root_dir, "mode": "z"},
            scripts_dir: {"bind": scripts_dir, "mode": "z"},
            config_dir: {"bind": self.config_dir, "mode": "z"},
            str(CODE_ROOT_DIR): {"bind": str(CODE_ROOT_DIR), "mode": "z"},
        }
        if "volumes" not in self.container_run_kwargs:
            self.container_run_kwargs["volumes"] = {}
        self.container_run_kwargs["volumes"].update(volumes)
        self.container_run_kwargs.setdefault("hostname", self.name)
        self.container_run_kwargs.setdefault("auto_remove", True)

    def build_cmdline(self, *args):
        return ["docker", "exec", "-i", self.name] + super().build_cmdline(*args)

    def start(self, *extra_cli_arguments, max_start_attempts=None, start_timeout=None):
        # Start the container
        ContainerFactory.start(
            self, max_start_attempts=max_start_attempts, start_timeout=start_timeout
        )
        self.daemon_starting = True
        # Now that the container is up, let's start the daemon
        self.daemon_started = SaltDaemonFactory.start(
            self,
            *extra_cli_arguments,
            max_start_attempts=max_start_attempts,
            start_timeout=start_timeout
        )
        return self.daemon_started

    def terminate(self):
        self.daemon_started = self.daemon_starting = False
        ret = SaltDaemonFactory.terminate(self)
        ContainerFactory.terminate(self)
        return ret

    def is_running(self):
        running = ContainerFactory.is_running(self)
        if running is False:
            return running
        if self.daemon_starting or self.daemon_started:
            return SaltDaemonFactory.is_running(self)
        return running

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError


@attr.s(kw_only=True, slots=True)
class SaltMinionContainerFactory(SaltDaemonContainerFactory, SaltMinionFactory):
    """
    Salt minion daemon implementation running in a docker container
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        return SaltMinionFactory.get_check_events(self)

    def run_start_checks(self, started_at, timeout_at):
        return SaltMinionFactory.run_start_checks(self, started_at, timeout_at)


@attr.s(kw_only=True, slots=True)
class SshdDaemonFactory(DaemonFactory):
    config_dir = attr.ib()
    listen_address = attr.ib(default=None)
    listen_port = attr.ib(default=None)
    authorized_keys = attr.ib(default=None)
    sshd_config_dict = attr.ib(default=None, repr=False)
    client_key = attr.ib(default=None, init=False, repr=False)
    sshd_config = attr.ib(default=None, init=False)

    def __attrs_post_init__(self):
        if self.authorized_keys is None:
            self.authorized_keys = []
        if self.sshd_config_dict is None:
            self.sshd_config_dict = {}
        if self.listen_address is None:
            self.listen_address = "127.0.0.1"
        if self.listen_port is None:
            self.listen_port = ports.get_unused_localhost_port()
        self.check_ports = [self.listen_port]
        if isinstance(self.config_dir, str):
            self.config_dir = pathlib.Path(self.config_dir)
        elif not isinstance(self.config_dir, pathlib.Path):
            # A py local path?
            self.config_dir = pathlib.Path(self.config_dir.strpath)
        self.config_dir.chmod(0o0700)
        authorized_keys_file = self.config_dir / "authorized_keys"

        # Let's generate the client key
        self.client_key = self._generate_client_ecdsa_key()
        with open("{}.pub".format(self.client_key)) as rfh:
            pubkey = rfh.read().strip()
            log.debug("SSH client pub key: %r", pubkey)
            self.authorized_keys.append(pubkey)

        # Write the authorized pub keys to file
        with open(str(authorized_keys_file), "w") as wfh:
            wfh.write("\n".join(self.authorized_keys))

        authorized_keys_file.chmod(0o0600)

        with open(str(authorized_keys_file)) as rfh:
            log.debug("AuthorizedKeysFile contents:\n%s", rfh.read())

        _default_config = {
            "ListenAddress": self.listen_address,
            "PermitRootLogin": "no",
            "ChallengeResponseAuthentication": "no",
            "PasswordAuthentication": "no",
            "PubkeyAuthentication": "yes",
            "PrintMotd": "no",
            "PidFile": self.config_dir / "sshd.pid",
            "AuthorizedKeysFile": authorized_keys_file,
        }
        if self.sshd_config_dict:
            _default_config.update(self.sshd_config_dict)
        self.sshd_config = _default_config
        self._write_config()
        super().__attrs_post_init__()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return [
            "-D",
            "-e",
            "-f",
            str(self.config_dir / "sshd_config"),
            "-p",
            str(self.listen_port),
        ]

    def _write_config(self):
        sshd_config_file = self.config_dir / "sshd_config"
        if not sshd_config_file.exists():
            # Let's write a default config file
            config_lines = []
            for key, value in self.sshd_config.items():
                if isinstance(value, list):
                    for item in value:
                        config_lines.append("{} {}\n".format(key, item))
                    continue
                config_lines.append("{} {}\n".format(key, value))

            # Let's generate the host keys
            self._generate_server_dsa_key()
            self._generate_server_ecdsa_key()
            self._generate_server_ed25519_key()
            for host_key in pathlib.Path(self.config_dir).glob("ssh_host_*_key"):
                config_lines.append("HostKey {}\n".format(host_key))

            with open(str(sshd_config_file), "w") as wfh:
                wfh.write("".join(sorted(config_lines)))
            sshd_config_file.chmod(0o0600)
            with open(str(sshd_config_file)) as wfh:
                log.debug(
                    "Wrote to configuration file %s. Configuration:\n%s",
                    sshd_config_file,
                    wfh.read(),
                )

    def _generate_client_ecdsa_key(self):
        key_filename = "client_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ecdsa", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_dsa_key(self):
        key_filename = "ssh_host_dsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "dsa", "1024")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_ecdsa_key(self):
        key_filename = "ssh_host_ecdsa_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ecdsa", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _generate_server_ed25519_key(self):
        key_filename = "ssh_host_ed25519_key"
        key_path_prv = self.config_dir / key_filename
        key_path_pub = self.config_dir / "{}.pub".format(key_filename)
        if key_path_prv.exists() and key_path_pub.exists():
            return key_path_prv
        self._ssh_keygen(key_filename, "ed25519", "521")
        for key_path in (key_path_prv, key_path_pub):
            key_path.chmod(0o0400)
        return key_path_prv

    def _ssh_keygen(self, key_filename, key_type, bits, comment=None):
        try:
            ssh_keygen = self._ssh_keygen_path
        except AttributeError:
            ssh_keygen = self._ssh_keygen_path = shutil.which("ssh-keygen")

        if comment is None:
            comment = "{user}@{host}-{date}".format(
                user=salt.utils.user.get_user(),
                host=socket.gethostname(),
                date=datetime.utcnow().strftime("%Y-%m-%d"),
            )

        cmdline = [
            ssh_keygen,
            "-t",
            key_type,
            "-b",
            bits,
            "-C",
            comment,
            "-f",
            key_filename,
            "-P",
            "",
        ]
        try:
            subprocess.run(
                cmdline,
                cwd=str(self.config_dir),
                check=True,
                universal_newlines=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            raise FactoryNotStarted(
                "Failed to generate ssh key.",
                cmdline=exc.args,
                stdout=exc.stdout,
                stderr=exc.stderr,
                exitcode=exc.returncode,
            )


@attr.s(kw_only=True, slots=True)
class SaltVirtMinionContainerFactory(SaltMinionContainerFactory):

    host_uuid = attr.ib(default=attr.Factory(uuid.uuid4))
    ssh_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )
    sshd_port = attr.ib(default=attr.Factory(ports.get_unused_localhost_port))
    libvirt_tcp_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )
    libvirt_tls_port = attr.ib(
        default=attr.Factory(ports.get_unused_localhost_port), repr=False
    )

    uri = attr.ib(init=False)
    ssh_uri = attr.ib(init=False)
    tcp_uri = attr.ib(init=False)
    tls_uri = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.uri = "localhost:{}".format(self.sshd_port)
        self.ssh_uri = "qemu+ssh://{}/system".format(self.uri)
        self.tcp_uri = "qemu+tcp://localhost:{}/system".format(self.libvirt_tcp_port)
        self.tls_uri = "qemu+tls://localhost:{}/system".format(self.libvirt_tls_port)

        if self.check_ports is None:
            self.check_ports = []
        self.check_ports.extend(
            [self.sshd_port, self.libvirt_tcp_port, self.libvirt_tls_port]
        )
        if "environment" not in self.container_run_kwargs:
            self.container_run_kwargs["environment"] = {}
        self.container_run_kwargs["environment"].update(
            {
                "SSH_PORT": str(self.ssh_port),
                "SSHD_PORT": str(self.sshd_port),
                "LIBVIRT_TCP_PORT": str(self.libvirt_tcp_port),
                "LIBVIRT_TLS_PORT": str(self.libvirt_tls_port),
                "NO_START_MINION": "1",
                "HOST_UUID": self.host_uuid,
            }
        )
        if "ports" not in self.container_run_kwargs:
            self.container_run_kwargs["ports"] = {}
        self.container_run_kwargs["ports"].update(
            {
                "{}/tcp".format(self.ssh_port): self.ssh_port,
                "{}/tcp".format(self.sshd_port): self.sshd_port,
                "{}/tcp".format(self.libvirt_tcp_port): self.libvirt_tcp_port,
                "{}/tcp".format(self.libvirt_tls_port): self.libvirt_tls_port,
            }
        )
        if "volumes" not in self.container_run_kwargs:
            self.container_run_kwargs["volumes"] = {}
        self.container_run_kwargs["volumes"].update(
            {
                RUNTIME_VARS.CODE_DIR: {"bind": "/salt", "mode": "z"},
                RUNTIME_VARS.CODE_DIR: {"bind": RUNTIME_VARS.CODE_DIR, "mode": "z"},
            }
        )
        self.container_run_kwargs["working_dir"] = RUNTIME_VARS.CODE_DIR
        self.container_run_kwargs["network_mode"] = "host"
        self.container_run_kwargs["cap_add"] = ["ALL"]
        self.container_run_kwargs["privileged"] = True
        super().__attrs_post_init__()
        self.python_executable = "python3"

    def _container_start_checks(self):
        # Once we're able to ls the salt-minion script it means the container
        # has salt installed
        ret = self.run("ls", "-lah", self.get_script_path())
        if ret.exitcode == 0:
            return True
        time.sleep(1)
        return False


@attr.s(kw_only=True, slots=True, hash=True)
class LogServer:
    log_host = attr.ib(default="0.0.0.0")
    log_port = attr.ib(default=attr.Factory(ports.get_unused_localhost_port))
    log_level = attr.ib()
    running_event = attr.ib(init=False, repr=False, hash=False)
    process_queue_thread = attr.ib(init=False, repr=False, hash=False)

    def start(self):
        log.info("Starting log server at %s:%d", self.log_host, self.log_port)
        self.running_event = threading.Event()
        self.process_queue_thread = threading.Thread(target=self.process_logs)
        self.process_queue_thread.start()
        # Wait for the thread to start
        if self.running_event.wait(5) is not True:
            self.running_event.clear()
            raise RuntimeError("Failed to start the log server")
        log.info("Log Server Started")

    def stop(self):
        log.info("Stopping the logging server")
        address = "tcp://{}:{}".format(self.log_host, self.log_port)
        log.debug("Stopping the multiprocessing logging queue listener at %s", address)
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect(address)
        try:
            sender.send(msgpack.dumps(None))
            log.info("Sent sentinel to trigger log server shutdown")
        finally:
            sender.close(1000)
            context.term()

        # Clear the running even, the log process thread know it should stop
        self.running_event.clear()
        log.info("Joining the logging server process thread")
        self.process_queue_thread.join(7)
        if not self.process_queue_thread.is_alive():
            log.debug("Stopped the log server")
        else:
            log.warning(
                "The logging server thread is still running. Waiting a little longer..."
            )
            self.process_queue_thread.join(5)
            if not self.process_queue_thread.is_alive():
                log.debug("Stopped the log server")
            else:
                log.warning("The logging server thread is still running...")

    def process_logs(self):
        address = "tcp://{}:{}".format(self.log_host, self.log_port)
        context = zmq.Context()
        puller = context.socket(zmq.PULL)
        exit_timeout_seconds = 5
        exit_timeout = None
        try:
            puller.bind(address)
        except zmq.ZMQError as exc:
            log.exception("Unable to bind to puller at %s", address)
            return
        try:
            self.running_event.set()
            while True:
                if not self.running_event.is_set():
                    if exit_timeout is None:
                        log.debug(
                            "Waiting %d seconds to process any remaning log messages "
                            "before exiting...",
                            exit_timeout_seconds,
                        )
                        exit_timeout = time.time() + exit_timeout_seconds

                    if time.time() >= exit_timeout:
                        log.debug(
                            "Unable to process remaining log messages in time. "
                            "Exiting anyway."
                        )
                        break
                try:
                    try:
                        msg = puller.recv(flags=zmq.NOBLOCK)
                    except zmq.ZMQError as exc:
                        if exc.errno != zmq.EAGAIN:
                            raise
                        time.sleep(0.25)
                        continue
                    if msgpack.version >= (0, 5, 2):
                        record_dict = msgpack.loads(msg, raw=False)
                    else:
                        record_dict = msgpack.loads(msg, encoding="utf-8")
                    if record_dict is None:
                        # A sentinel to stop processing the queue
                        log.info("Received the sentinel to shutdown the log server")
                        break
                    try:
                        record_dict["message"]
                    except KeyError:
                        # This log record was msgpack dumped from Py2
                        for key, value in record_dict.copy().items():
                            skip_update = True
                            if isinstance(value, bytes):
                                value = value.decode("utf-8")
                                skip_update = False
                            if isinstance(key, bytes):
                                key = key.decode("utf-8")
                                skip_update = False
                            if skip_update is False:
                                record_dict[key] = value
                    # Just log everything, filtering will happen on the main process
                    # logging handlers
                    record = logging.makeLogRecord(record_dict)
                    logger = logging.getLogger(record.name)
                    logger.handle(record)
                except (EOFError, KeyboardInterrupt, SystemExit) as exc:
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    log.warning(
                        "An exception occurred in the log server processing queue thread: %s",
                        exc,
                        exc_info=True,
                    )
        finally:
            puller.close(1)
            context.term()
