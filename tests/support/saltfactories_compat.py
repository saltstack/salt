"""
    saltfactories.utils.processes.salts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Salt's related daemon classes and CLI processes implementations
"""
import atexit
import json
import logging
import os
import pprint
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import weakref
from collections import namedtuple
from operator import itemgetter

import psutil  # pylint: disable=3rd-party-module-not-gated
import pytest
import salt.client
from saltfactories.exceptions import FactoryTimeout as ProcessTimeout
from saltfactories.utils.processes import terminate_process

SALT_KEY_LOG_LEVEL_SUPPORTED = False
log = logging.getLogger(__name__)


class Popen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        for key in ("stdout", "stderr"):
            if key in kwargs:
                raise RuntimeError(
                    "{}.Popen() does not accept {} as a valid keyword argument".format(
                        __name__, key
                    )
                )
        stdout = tempfile.SpooledTemporaryFile(512000)
        kwargs["stdout"] = stdout
        stderr = tempfile.SpooledTemporaryFile(512000)
        kwargs["stderr"] = stderr
        super().__init__(*args, **kwargs)
        self.__stdout = stdout
        self.__stderr = stderr
        weakref.finalize(self, stdout.close)
        weakref.finalize(self, stderr.close)

    def communicate(self, input=None):  # pylint: disable=arguments-differ
        super().communicate(input)
        stdout = stderr = None
        if self.__stdout:
            self.__stdout.flush()
            self.__stdout.seek(0)
            stdout = self.__stdout.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stdout = stdout.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        if self.__stderr:
            self.__stderr.flush()
            self.__stderr.seek(0)
            stderr = self.__stderr.read()

            # We want str type on Py3 and Unicode type on Py2
            # pylint: disable=undefined-variable
            stderr = stderr.decode(__salt_system_encoding__)
            # pylint: enable=undefined-variable
        return stdout, stderr


class ProcessResult(
    namedtuple("ProcessResult", ("exitcode", "stdout", "stderr", "cmdline"))
):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr, cmdline=None):
        if not isinstance(exitcode, int):
            raise ValueError(
                "'exitcode' needs to be an integer, not '{}'".format(type(exitcode))
            )
        return super().__new__(cls, exitcode, stdout, stderr, cmdline=cmdline)

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ProcessResult exit code property")
    stdout = property(itemgetter(1), doc="ProcessResult stdout property")
    stderr = property(itemgetter(2), doc="ProcessResult stderr property")
    cmdline = property(itemgetter(3), doc="ProcessResult cmdline property")

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(
                self.stdout
            )
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(
                self.stderr
            )
        return message + "\n"


class ShellResult(
    namedtuple("ShellResult", ("exitcode", "stdout", "stderr", "json", "cmdline"))
):
    """
    This class serves the purpose of having a common result class which will hold the
    resulting data from a subprocess command.
    """

    __slots__ = ()

    def __new__(cls, exitcode, stdout, stderr, json=None, cmdline=None):
        if not isinstance(exitcode, int):
            raise ValueError(
                "'exitcode' needs to be an integer, not '{}'".format(type(exitcode))
            )
        return super().__new__(
            cls, exitcode, stdout, stderr, json=json, cmdline=cmdline
        )

    # These are copied from the namedtuple verbose output in order to quiet down PyLint
    exitcode = property(itemgetter(0), doc="ShellResult exit code property")
    stdout = property(itemgetter(1), doc="ShellResult stdout property")
    stderr = property(itemgetter(2), doc="ShellResult stderr property")
    json = property(
        itemgetter(3), doc="ShellResult stdout JSON decoded, when parseable."
    )
    cmdline = property(itemgetter(4), doc="ShellResult cmdline property")

    def __str__(self):
        message = self.__class__.__name__
        if self.cmdline:
            message += "\n Command Line: {}".format(self.cmdline)
        if self.exitcode is not None:
            message += "\n Exitcode: {}".format(self.exitcode)
        if self.stdout or self.stderr:
            message += "\n Process Output:"
        if self.stdout:
            message += "\n   >>>>> STDOUT >>>>>\n{}\n   <<<<< STDOUT <<<<<".format(
                self.stdout
            )
        if self.stderr:
            message += "\n   >>>>> STDERR >>>>>\n{}\n   <<<<< STDERR <<<<<".format(
                self.stderr
            )
        if self.json:
            message += "\n JSON Object:\n"
            message += "".join(
                "  {}".format(line) for line in pprint.pformat(self.json)
            )
        return message + "\n"

    def __eq__(self, other):
        """
        Allow comparison against the parsed JSON or the output
        """
        if self.json:
            return self.json == other
        return self.stdout == other


class FactoryProcess:
    """
    Base class for subprocesses
    """

    def __init__(
        self,
        cli_script_name,
        slow_stop=True,
        environ=None,
        cwd=None,
        base_script_args=None,
    ):
        """

        Args:
            cli_script_name(str):
                This is the string containing the name of the binary to call on the subprocess, either the
                full path to it, or the basename. In case of the basename, the directory containing the
                basename must be in your ``$PATH`` variable.
            slow_stop(bool):
                Wether to terminate the processes by sending a :py:attr:`SIGTERM` signal or by calling
                :py:meth:`~subprocess.Popen.terminate` on the sub-procecess.
                When code coverage is enabled, one will want `slow_stop` set to `True` so that coverage data
                can be written down to disk.
            environ(dict):
                A dictionary of `key`, `value` pairs to add to the environment.
            cwd (str):
                The path to the current working directory
            base_script_args(list or tuple):
                An list or tuple iterable of the base arguments to use when building the command line to
                launch the process
        """
        self.cli_script_name = cli_script_name
        self.slow_stop = slow_stop
        self.environ = environ or os.environ.copy()
        self.cwd = cwd or os.getcwd()
        self._terminal = None
        self._terminal_result = None
        self._terminal_timeout = None
        self._children = []
        self._base_script_args = base_script_args

    def get_display_name(self):
        """
        Returns a name to show when process stats reports are enabled
        """
        return self.cli_script_name

    def get_log_prefix(self):
        """
        Returns the log prefix that shall be used for a salt daemon forwarding log records.
        It is also used by :py:func:`start_daemon` when starting the daemon subprocess.
        """
        return "[{}] ".format(self.cli_script_name)

    def get_script_path(self):
        """
        Returns the path to the script to run
        """
        if os.path.isabs(self.cli_script_name):
            script_path = self.cli_script_name
        else:
            script_path = salt.utils.path.which(self.cli_script_name)
        if not os.path.exists(script_path):
            pytest.fail("The CLI script {!r} does not exist".format(script_path))
        return script_path

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if self._base_script_args:
            return list(self._base_script_args)
        return []

    def get_script_args(self):  # pylint: disable=no-self-use
        """
        Returns any additional arguments to pass to the CLI script
        """
        return []

    def build_cmdline(self, *args, **kwargs):
        return (
            [self.get_script_path()]
            + self.get_base_script_args()
            + self.get_script_args()
            + list(args)
        )

    def init_terminal(self, cmdline, **kwargs):
        """
        Instantiate a terminal with the passed cmdline and kwargs and return it.

        Additionaly, it sets a reference to it in self._terminal and also collects
        an initial listing of child processes which will be used when terminating the
        terminal
        """
        self._terminal = Popen(cmdline, **kwargs)
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

    def terminate(self):
        """
        Terminate the started daemon
        """
        if self._terminal is None:
            return self._terminal_result
        log.info("%sStopping %s", self.get_log_prefix(), self.__class__.__name__)
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
        # Lets log and kill any child processes which salt left behind
        terminate_process(
            pid=self._terminal.pid,
            kill_children=True,
            children=self._children,
            slow_stop=self.slow_stop,
        )
        stdout, stderr = self._terminal.communicate()
        try:
            log_message = "{}Terminated {}.".format(
                self.get_log_prefix(), self.__class__.__name__
            )
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
            self._children = []

    @property
    def pid(self):
        terminal = getattr(self, "_terminal", None)
        if not terminal:
            return
        return terminal.pid

    def __repr__(self):
        return "<{} display_name='{}'>".format(
            self.__class__.__name__, self.get_display_name()
        )


class FactoryScriptBase(FactoryProcess):
    """
    Base class for CLI scripts
    """

    def __init__(self, *args, **kwargs):
        """
        Base class for non daemonic CLI processes

        Check base class(es) for additional supported parameters

        Args:
            default_timeout(int):
                The maximum ammount of seconds that a script should run
        """
        default_timeout = kwargs.pop("default_timeout", None)
        super().__init__(*args, **kwargs)
        if default_timeout is None:
            if not sys.platform.startswith(("win", "darwin")):
                default_timeout = 30
            else:
                # Windows and macOS are just slower.
                default_timeout = 120
        self.default_timeout = default_timeout
        self._terminal_timeout_set_explicitly = False

    def run(self, *args, **kwargs):
        """
        Run the given command synchronously
        """
        start_time = time.time()
        timeout = kwargs.pop("_timeout", None)

        # Build the cmdline to pass to the terminal
        # We set the _terminal_timeout attribute while calling build_cmdline in case it needs
        # access to that information to build the command line
        self._terminal_timeout = timeout or self.default_timeout
        self._terminal_timeout_set_explicitly = timeout is not None
        cmdline = self.build_cmdline(*args, **kwargs)
        timeout_expire = time.time() + self._terminal_timeout

        log.info(
            "%sRunning %r in CWD: %s ...", self.get_log_prefix(), cmdline, self.cwd
        )

        terminal = self.init_terminal(cmdline, cwd=self.cwd, env=self.environ,)
        timmed_out = False
        while True:
            if timeout_expire < time.time():
                timmed_out = True
                break
            if terminal.poll() is not None:
                break
            time.sleep(0.25)

        result = self.terminate()
        if timmed_out:
            raise ProcessTimeout(
                "{}Failed to run: {}; Error: Timed out after {:.2f} seconds!".format(
                    self.get_log_prefix(), cmdline, time.time() - start_time
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                cmdline=cmdline,
                exitcode=result.exitcode,
            )

        exitcode = result.exitcode
        stdout, stderr, json_out = self.process_output(
            result.stdout, result.stderr, cmdline=cmdline
        )
        log.info(
            "%sCompleted %r in CWD: %s after %.2f seconds",
            self.get_log_prefix(),
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
                    "%sFailed to load JSON from the following output:\n%r",
                    self.get_log_prefix(),
                    stdout,
                )
                json_out = None
        else:
            json_out = None
        return stdout, stderr, json_out


class FactoryPythonScriptBase(FactoryScriptBase):
    def __init__(self, *args, **kwargs):
        """
        Base class for python scripts based CLI processes

        Check base class(es) for additional supported parameters

        Args:
            python_executable(str):
                The path to the python executable to use
        """
        python_executable = kwargs.pop("python_executable", None)
        super().__init__(*args, **kwargs)
        self.python_executable = python_executable or sys.executable
        # We really do not want buffered output
        self.environ.setdefault("PYTHONUNBUFFERED", "1")
        # Don't write .pyc files or create them in __pycache__ directories
        self.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    def build_cmdline(self, *args, **kwargs):
        cmdline = super().build_cmdline(*args, **kwargs)
        if cmdline[0] != self.python_executable:
            cmdline.insert(0, self.python_executable)
        return cmdline


class FactoryDaemonScriptBase(FactoryProcess):
    def is_alive(self):
        """
        Returns true if the process is alive
        """
        terminal = getattr(self, "_terminal", None)
        if not terminal:
            return False
        return terminal.poll() is None

    def get_check_ports(self):  # pylint: disable=no-self-use
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return []

    def start(self):
        """
        Start the daemon subprocess
        """
        log.info(
            "%sStarting DAEMON %s in CWD: %s",
            self.get_log_prefix(),
            self.cli_script_name,
            self.cwd,
        )
        cmdline = self.build_cmdline()

        log.info("%sRunning %r...", self.get_log_prefix(), cmdline)

        self.init_terminal(
            cmdline, env=self.environ, cwd=self.cwd,
        )
        self._children.extend(psutil.Process(self.pid).children(recursive=True))
        return True


class SaltConfigMixin:
    @property
    def config_dir(self):
        if "conf_file" in self.config:
            return os.path.dirname(self.config["conf_file"])

    @property
    def config_file(self):
        if "conf_file" in self.config:
            return self.config["conf_file"]

    def __repr__(self):
        return "<{} id='{id}' role='{__role}'>".format(
            self.__class__.__name__, **self.config
        )


class SaltScriptBase(FactoryPythonScriptBase, SaltConfigMixin):

    __cli_timeout_supported__ = False
    __cli_log_level_supported__ = True

    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        hard_crash = kwargs.pop("salt_hard_crash", False)
        super().__init__(*args, **kwargs)
        self.config = config
        self.hard_crash = hard_crash

    def get_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        if not self.hard_crash:
            return super().get_script_args()
        return ["--hard-crash"]

    def get_minion_tgt(self, kwargs):
        minion_tgt = None
        if "minion_tgt" in kwargs:
            minion_tgt = kwargs.pop("minion_tgt")
        return minion_tgt

    def build_cmdline(self, *args, **kwargs):  # pylint: disable=arguments-differ
        log.debug("Building cmdline. Input args: %s; Input kwargs: %s;", args, kwargs)
        minion_tgt = self._minion_tgt = self.get_minion_tgt(kwargs)
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

        # Add the remaning args
        cmdline.extend(args)

        for key in kwargs:
            value = kwargs[key]
            if not isinstance(value, str):
                value = json.dumps(value)
            cmdline.append("{}={}".format(key, value))
        cmdline = super().build_cmdline(*cmdline)
        log.debug("Built cmdline: %s", cmdline)
        return cmdline

    def process_output(self, stdout, stderr, cmdline=None):
        stdout, stderr, json_out = super().process_output(
            stdout, stderr, cmdline=cmdline
        )
        if json_out and isinstance(json_out, str) and "--out=json" in cmdline:
            # Sometimes the parsed JSON is just a string, for example:
            #  OUTPUT: '"The salt master could not be contacted. Is master running?"\n'
            #  LOADED JSON: 'The salt master could not be contacted. Is master running?'
            #
            # In this case, we assign the loaded JSON to stdout and reset json_out
            stdout = json_out
            json_out = None
        return stdout, stderr, json_out


class SaltDaemonScriptBase(
    FactoryDaemonScriptBase, FactoryPythonScriptBase, SaltConfigMixin
):
    def __init__(self, *args, **kwargs):
        config = kwargs.pop("config", None) or {}
        extra_checks_callback = kwargs.pop("extra_checks_callback", None)
        super().__init__(*args, **kwargs)
        self.config = config
        self.extra_checks_callback = extra_checks_callback

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        config_dir = self.config_dir
        if config_dir:
            script_args.append("--config-dir={}".format(config_dir))
        script_args.append("--log-level=quiet")
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        raise NotImplementedError

    def get_log_prefix(self):
        """
        Returns the log prefix that shall be used for a salt daemon forwarding log records.
        It is also used by :py:func:`start_daemon` when starting the daemon subprocess.
        """
        try:
            return self._log_prefix
        except AttributeError:
            try:
                pytest_config_key = "pytest-{}".format(self.config["__role"])
                log_prefix = (
                    self.config.get(pytest_config_key, {}).get("log", {}).get("prefix")
                    or ""
                )
                if log_prefix:
                    self._log_prefix = "[{}] ".format(
                        log_prefix.format(
                            cli_name=os.path.basename(self.cli_script_name)
                        )
                    )
            except KeyError:
                # This should really be a salt daemon which always set's `__role` in its config
                self._log_prefix = super().get_log_prefix()
        return self._log_prefix

    def get_display_name(self):
        """
        Returns a name to show when process stats reports are enabled
        """
        try:
            return self._display_name
        except AttributeError:
            self._display_name = self.get_log_prefix().strip().lstrip("[").rstrip("]")
        return self._display_name

    def run_extra_checks(self, salt_factories):
        """
        This extra check is here so that we confirm the daemon is up as soon as it get's responsive
        """
        if self.extra_checks_callback is None:
            return True
        return self.extra_checks_callback(salt_factories, self.config)


class SaltMaster(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt master daemon
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        yield self.config["id"], "salt/master/{id}/start".format(**self.config)


class SaltMinion(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(
            **self.config
        )


class SaltSyndic(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt minion daemon
    """

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(
            **self.config
        )


class SaltProxyMinion(SaltDaemonScriptBase):
    """
    Simple subclass to define a salt proxy minion daemon
    """

    def __init__(self, *args, **kwargs):
        include_proxyid_cli_flag = kwargs.pop("include_proxyid_cli_flag", True)
        super().__init__(*args, **kwargs)
        self.include_proxyid_cli_flag = include_proxyid_cli_flag

    def get_base_script_args(self):
        script_args = super().get_base_script_args()
        if sys.platform.startswith("win") is False:
            script_args.append("--disable-keepalive")
        if self.include_proxyid_cli_flag is True:
            script_args.extend(["--proxyid", self.config["id"]])
        return script_args

    def get_check_events(self):
        """
        Return a list of tuples in the form of `(master_id, event_tag)` check against to ensure the daemon is running
        """
        pytest_config = self.config["pytest-{}".format(self.config["__role"])]
        yield pytest_config["master_config"]["id"], "salt/{__role}/{id}/start".format(
            **self.config
        )


class SaltCLI(SaltScriptBase):
    """
    Simple subclass to the salt CLI script
    """

    __cli_timeout_supported__ = True

    def process_output(self, stdout, stderr, cmdline=None):
        if (
            "No minions matched the target. No command was sent, no jid was assigned.\n"
            in stdout
        ):
            stdout = stdout.split("\n", 1)[1:][0]
        old_stdout = None
        if "--show-jid" in cmdline and stdout.startswith("jid: "):
            old_stdout = stdout
            stdout = stdout.split("\n", 1)[-1].strip()
        stdout, stderr, json_out = SaltScriptBase.process_output(
            self, stdout, stderr, cmdline
        )
        if old_stdout is not None:
            stdout = old_stdout
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltCallCLI(SaltScriptBase):
    """
    Simple subclass to the salt-call CLI script
    """

    __cli_timeout_supported__ = True

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # Under salt-call, the minion target is always "local"
        self._minion_tgt = "local"
        stdout, stderr, json_out = SaltScriptBase.process_output(
            self, stdout, stderr, cmdline
        )
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltRunCLI(SaltScriptBase):
    """
    Simple subclass to the salt-run CLI script
    """

    __cli_timeout_supported__ = True

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        if (
            "No minions matched the target. No command was sent, no jid was assigned.\n"
            in stdout
        ):
            stdout = stdout.split("\n", 1)[1:][0]
        return super().process_output(stdout, stderr, cmdline=cmdline)


class SaltCpCLI(SaltScriptBase):
    """
    Simple subclass to the salt-cp CLI script
    """

    __cli_timeout_supported__ = True

    def process_output(self, stdout, stderr, cmdline=None):
        if (
            "No minions matched the target. No command was sent, no jid was assigned.\n"
            in stdout
        ):
            stdout = stdout.split("\n", 1)[1:][0]
        stdout, stderr, json_out = SaltScriptBase.process_output(
            self, stdout, stderr, cmdline
        )
        if json_out:
            try:
                return stdout, stderr, json_out[self._minion_tgt]
            except KeyError:
                return stdout, stderr, json_out
        return stdout, stderr, json_out


class SaltKeyCLI(SaltScriptBase):
    """
    Simple subclass to the salt-key CLI script
    """

    _output_replace_re = re.compile(
        r"((The following keys are going to be.*:|Key for minion.*)\n)"
    )

    # As of Neon, salt-key still does not support --log-level
    # Only when we get the new logging merged in will we get that, so remove that CLI flag
    __cli_log_level_supported__ = SALT_KEY_LOG_LEVEL_SUPPORTED

    def get_minion_tgt(self, kwargs):
        return None

    def process_output(self, stdout, stderr, cmdline=None):
        # salt-key print()s to stdout regardless of output chosen
        stdout = self._output_replace_re.sub("", stdout)
        return super().process_output(stdout, stderr, cmdline=cmdline)


SCRIPT_TEMPLATES = {
    "salt": textwrap.dedent(
        """
        import atexit
        from salt.scripts import salt_main

        if __name__ == '__main__':
            exitcode = 0
            try:
                salt_main()
            except SystemExit as exc:
                exitcode = exc.code
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "salt-api": textwrap.dedent(
        """
        import atexit
        import salt.cli

        def main():
            sapi = salt.cli.SaltAPI()
            sapi.start()

        if __name__ == '__main__':
            exitcode = 0
            try:
                main()
            except SystemExit as exc:
                exitcode = exc.code
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "common": textwrap.dedent(
        """
        import atexit
        from salt.scripts import salt_{0}
        import salt.utils.platform

        def main():
            if salt.utils.platform.is_windows():
                import os.path
                import py_compile
                cfile = os.path.splitext(__file__)[0] + '.pyc'
                if not os.path.exists(cfile):
                    py_compile.compile(__file__, cfile)
            salt_{0}()

        if __name__ == '__main__':
            exitcode = 0
            try:
                main()
            except SystemExit as exc:
                exitcode = exc.code
            sys.stdout.flush()
            sys.stderr.flush()
            atexit._run_exitfuncs()
            os._exit(exitcode)
        """
    ),
    "coverage": textwrap.dedent(
        """
        # Setup coverage environment variables
        COVERAGE_FILE = os.path.join(CODE_DIR, '.coverage')
        COVERAGE_PROCESS_START = os.path.join(CODE_DIR, '.coveragerc')
        os.environ[str('COVERAGE_FILE')] = str(COVERAGE_FILE)
        os.environ[str('COVERAGE_PROCESS_START')] = str(COVERAGE_PROCESS_START)
        """
    ),
    "sitecustomize": textwrap.dedent(
        """
        # Allow sitecustomize.py to be importable for test coverage purposes
        SITECUSTOMIZE_DIR = r'{sitecustomize_dir}'
        PYTHONPATH = os.environ.get('PYTHONPATH') or None
        if PYTHONPATH is None:
            PYTHONPATH_ENV_VAR = SITECUSTOMIZE_DIR
        else:
            PYTHON_PATH_ENTRIES = PYTHONPATH.split(os.pathsep)
            if SITECUSTOMIZE_DIR in PYTHON_PATH_ENTRIES:
                PYTHON_PATH_ENTRIES.remove(SITECUSTOMIZE_DIR)
            PYTHON_PATH_ENTRIES.insert(0, SITECUSTOMIZE_DIR)
            PYTHONPATH_ENV_VAR = os.pathsep.join(PYTHON_PATH_ENTRIES)
        os.environ[str('PYTHONPATH')] = str(PYTHONPATH_ENV_VAR)
        if SITECUSTOMIZE_DIR in sys.path:
            sys.path.remove(SITECUSTOMIZE_DIR)
        sys.path.insert(0, SITECUSTOMIZE_DIR)
        """
    ),
}


def generate_script(
    bin_dir,
    script_name,
    executable=None,
    code_dir=None,
    inject_coverage=False,
    inject_sitecustomize=False,
):
    """
    Generate script
    """
    if not os.path.isdir(bin_dir):
        os.makedirs(bin_dir)

    cli_script_name = "cli_{}.py".format(script_name.replace("-", "_"))
    script_path = os.path.join(bin_dir, cli_script_name)

    if not os.path.isfile(script_path):
        log.info("Generating %s", script_path)

        with salt.utils.files.fopen(script_path, "w") as sfh:
            script_template = SCRIPT_TEMPLATES.get(script_name, None)
            if script_template is None:
                script_template = SCRIPT_TEMPLATES.get("common", None)

            if executable and len(executable) > 128:
                # Too long for a shebang, let's use /usr/bin/env and hope
                # the right python is picked up
                executable = "/usr/bin/env python"

            script_contents = (
                textwrap.dedent(
                    """
                #!{executable}

                from __future__ import absolute_import
                import os
                import sys

                # We really do not want buffered output
                os.environ[str("PYTHONUNBUFFERED")] = str("1")
                # Don't write .pyc files or create them in __pycache__ directories
                os.environ[str("PYTHONDONTWRITEBYTECODE")] = str("1")
                """.format(
                        executable=executable or sys.executable
                    )
                ).strip()
                + "\n\n"
            )

            if code_dir:
                script_contents += (
                    textwrap.dedent(
                        """
                    CODE_DIR = r'{code_dir}'
                    if CODE_DIR in sys.path:
                        sys.path.remove(CODE_DIR)
                    sys.path.insert(0, CODE_DIR)""".format(
                            code_dir=code_dir
                        )
                    ).strip()
                    + "\n\n"
                )

            if inject_coverage and not code_dir:
                raise RuntimeError(
                    "The inject coverage code needs to know the code root to find the "
                    "path to the '.coveragerc' file. Please pass 'code_dir'."
                )
            if inject_coverage:
                script_contents += SCRIPT_TEMPLATES["coverage"].strip() + "\n\n"

            if inject_sitecustomize:
                script_contents += (
                    SCRIPT_TEMPLATES["sitecustomize"]
                    .format(
                        sitecustomize_dir=os.path.join(
                            os.path.dirname(__file__), "coverage"
                        )
                    )
                    .strip()
                    + "\n\n"
                )

            script_contents += (
                script_template.format(
                    script_name.replace("salt-", "").replace("-", "_")
                ).strip()
                + "\n"
            )
            sfh.write(script_contents)
            log.debug(
                "Wrote the following contents to temp script %s:\n%s",
                script_path,
                script_contents,
            )
        fst = os.stat(script_path)
        os.chmod(script_path, fst.st_mode | stat.S_IEXEC)

    log.info("Returning script path %r", script_path)
    return script_path
