"""
Classes for starting/stopping/status salt daemons, auxiliary
scripts, generic commands.
"""


import atexit
import copy
import errno
import getpass
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta

import pytest
import salt.defaults.exitcodes as exitcodes
import salt.utils.files
import salt.utils.platform
import salt.utils.process
import salt.utils.psutil_compat as psutils
import salt.utils.yaml
from saltfactories.utils.processes import terminate_process, terminate_process_list
from tests.support.cli_scripts import ScriptPathMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


if "TimeoutError" not in __builtins__:

    class TimeoutError(OSError):
        """Compatibility exception with python3"""

    __builtins__["TimeoutError"] = TimeoutError


@pytest.mark.windows_whitelisted
class TestProgramMeta(type):
    """
    Stack all inherited config_attrs and dirtree dirs from the base classes.
    """

    def __new__(mcs, name, bases, attrs):
        config_vals = {}
        config_attrs = set()
        dirtree = set()

        for base in bases:
            config_vals.update(getattr(base, "config_vals", {}))
            config_attrs.update(getattr(base, "config_attrs", {}))
            dirtree.update(getattr(base, "dirtree", []))

        config_vals.update(attrs.get("config_vals", {}))
        attrs["config_vals"] = config_vals

        config_attrs.update(attrs.get("config_attrs", {}))
        attrs["config_attrs"] = config_attrs

        dirtree.update(attrs.get("dirtree", []))
        attrs["dirtree"] = dirtree

        return super().__new__(mcs, name, bases, attrs)


# pylint: disable=too-many-instance-attributes
@pytest.mark.windows_whitelisted
class TestProgram(metaclass=TestProgramMeta):
    """
    Set up an arbitrary executable to run.

    :attribute dirtree: An iterable of directories to be created
    """

    empty_config = ""
    config_file = ""

    config_attrs = {"name", "test_dir", "config_dirs"}
    config_vals = {}
    config_base = ""
    config_dir = os.path.join("etc")
    configs = {}
    config_types = (
        str,
        (str,),
    )

    dirtree = [
        "&config_dirs",
    ]

    @staticmethod
    def config_caster(cfg):
        return str(cfg)

    def __init__(
        self,
        program=None,
        name=None,
        env=None,
        shell=False,
        parent_dir=None,
        clean_on_exit=True,
        **kwargs
    ):
        self.program = program or getattr(self, "program", None)
        self.name = name or getattr(self, "name", "")
        self.env = env or {}
        self.shell = shell
        self._parent_dir = parent_dir or None
        self.clean_on_exit = clean_on_exit
        self._root_dir = kwargs.pop("root_dir", self.name)
        config_dir = kwargs.pop("config_dir", None)
        if config_dir is None:
            config_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.config_dir = config_dir

        config_attrs = copy.copy(self.config_attrs)
        config_attrs.update(kwargs.pop("config_attrs", set()))
        self.config_attrs = config_attrs

        config_vals = copy.copy(self.config_vals)
        config_vals.update(kwargs.pop("config_vals", {}))
        self.config_vals = config_vals

        config_base = copy.deepcopy(self.config_base)
        config_base = self.config_merge(
            config_base, kwargs.pop("config_base", self.config_types[0]())
        )
        self.config_base = config_base

        configs = copy.deepcopy(self.configs)
        for cname, cinfo in kwargs.pop("configs", {}).items():
            target = configs.setdefault(cname, {})
            if "path" in cinfo:
                target["path"] = cinfo["path"]
            if "map" in cinfo:
                target_map = target.setdefault("map", self.config_types[0]())
                target_map = self.config_merge(target_map, cinfo["map"])
                target["map"] = target_map
        self.configs = configs

        if not self.name:
            if not self.program:
                raise ValueError(
                    '"{}" object must specify "program" parameter'.format(
                        self.__class__.__name__
                    )
                )
            self.name = os.path.basename(self.program)

        self.process = None
        self.created_parent_dir = False
        self._setup_done = False

        dirtree = set(self.dirtree)
        dirtree.update(kwargs.pop("dirtree", []))
        self.dirtree = dirtree

        # Register the exit clean-up before making anything needing clean-up
        atexit.register(self.cleanup)

    def __enter__(self):
        pass

    def __exit__(self, typ, value, traceback):
        pass

    @property
    def test_dir(self):
        """Directory that will contains all of the static and dynamic files for the daemon"""
        return os.path.join(self.parent_dir, self._root_dir)

    def config_file_get(self, config):
        """Get the filename (viz. path) to the configuration file"""
        cfgf = self.configs[config].get("path")
        if cfgf:
            cfgf.format(**self.config_subs())
        else:
            cfgf = os.path.join(self.config_dir, config)
        return cfgf

    def config_dir_get(self, config):
        """Get the parent directory for the configuration file"""
        return os.path.dirname(self.config_file_get(config))

    @property
    def config_dirs(self):
        """Return a list of configuration directories"""
        cdirs = [self.config_dir_get(config) for config in self.configs.keys()]
        return cdirs

    def abs_path(self, path):
        """Absolute path of file including the test_dir"""
        return os.path.join(self.test_dir, path)

    @property
    def start_pid(self):
        """PID of the called script prior to daemonizing."""
        return self.process.pid if self.process else None

    @property
    def parent_dir(self):
        """
        Directory that contains everything generated for running scripts - possibly
        for multiple scripts.
        """
        if self._parent_dir is None:
            self.created_parent_dir = True
            self._parent_dir = tempfile.mkdtemp(prefix="salt-testdaemon-")
        else:
            self._parent_dir = os.path.abspath(os.path.normpath(self._parent_dir))
            if not os.path.exists(self._parent_dir):
                self.created_parent_dir = True
                os.makedirs(self._parent_dir)
            elif not os.path.isdir(self._parent_dir):
                raise ValueError(
                    'Parent path "{}" exists but is not a directory'.format(
                        self._parent_dir
                    )
                )
        return self._parent_dir

    def config_write(self, config):
        """Write out the config to a file"""
        if not config:
            return
        cpath = self.abs_path(self.config_file_get(config))
        with salt.utils.files.fopen(cpath, "w") as cfo:
            cfg = self.config_stringify(config)
            log.debug(
                "Writing configuration for {} to {}:\n{}".format(self.name, cpath, cfg)
            )
            cfo.write(cfg)
            cfo.flush()

    def configs_write(self):
        """Write all configuration files"""
        for config in self.configs:
            self.config_write(config)

    def config_type(self, config):
        """Check if a configuration is an acceptable type."""
        return isinstance(config, self.config_types)

    def config_cast(self, config):
        """Cast a configuration to the internal expected type."""
        if not self.config_type(config):
            config = self.config_caster(config)
        return config

    def config_subs(self):
        """Get the substitution values for use to generate the config"""
        subs = {attr: getattr(self, attr, None) for attr in self.config_attrs}
        for key, val in self.config_vals.items():
            subs[key] = val.format(**subs)
        return subs

    def config_stringify(self, config):
        """Get the configuration as a string"""
        cfg = self.config_get(config)
        cfg.format(**self.config_subs())
        return cfg

    def config_merge(self, base, overrides):
        """Merge two configuration hunks"""
        base = self.config_cast(base)
        overrides = self.config_cast(overrides)
        return "".join([base, overrides])

    def config_get(self, config):
        """Get the configuration data"""
        return self.configs[config]

    def config_set(self, config, val):
        """Set the configuration data"""
        self.configs[config] = val

    def make_dirtree(self):
        """Create directory structure."""
        subdirs = []
        for branch in self.dirtree:
            log.debug("checking dirtree: {}".format(branch))
            if not branch:
                continue
            if isinstance(branch, str) and branch[0] == "&":
                log.debug('Looking up dirtree branch "{}"'.format(branch))
                try:
                    dirattr = getattr(self, branch[1:], None)
                    log.debug('dirtree "{}" => "{}"'.format(branch, dirattr))
                except AttributeError:
                    raise ValueError(
                        'Unable to find dirtree attribute "{}" on object "{}.name = {}: {}"'.format(
                            branch, self.__class__.__name__, self.name, dir(self),
                        )
                    )

                if not dirattr:
                    continue

                if isinstance(dirattr, str):
                    subdirs.append(dirattr)
                elif hasattr(dirattr, "__iter__"):
                    subdirs.extend(dirattr)
                else:
                    raise TypeError(
                        "Branch type of {} in dirtree is unhandled".format(branch)
                    )
            elif isinstance(branch, str):
                subdirs.append(branch)
            else:
                raise TypeError(
                    "Branch type of {} in dirtree is unhandled".format(branch)
                )

        for subdir in subdirs:
            path = self.abs_path(subdir)
            if not os.path.exists(path):
                log.debug("make_dirtree: {}".format(path))
                os.makedirs(path)

    def setup(self, *args, **kwargs):
        """Create any scaffolding for run-time"""

        # unused
        _ = args, kwargs

        if not self._setup_done:
            self.make_dirtree()
            self.configs_write()
            self._setup_done = True

    def cleanup(self, *args, **kwargs):
        """ Clean out scaffolding of setup() and any run-time generated files."""
        # Unused for now
        _ = (args, kwargs)

        if self.process:
            try:
                self.process.kill()
                self.process.wait()
            except OSError:
                pass
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if self.created_parent_dir and os.path.exists(self.parent_dir):
            shutil.rmtree(self.parent_dir)

    def run(
        self,
        args=None,
        catch_stderr=False,
        with_retcode=False,
        timeout=None,
        raw=False,
        env=None,
        verbatim_args=False,
        verbatim_env=False,
    ):
        """
        Execute a command possibly using a supplied environment.

        :param args:
            A command string or a command sequence of arguments for the program.

        :param catch_stderr: A boolean whether to capture and return stderr.

        :param with_retcode: A boolean whether to return the exit code.

        :param timeout: A float of how long to wait for the process to
            complete before it is killed.

        :param raw: A boolean whether to return buffer strings for stdout and
            stderr or sequences of output lines.

        :param env: A dictionary of environment key/value settings for the
            command.

        :param verbatim_args: A boolean whether to automatically add inferred arguments.

        :param verbatim_env: A boolean whether to automatically add inferred
            environment values.

        :return list: (stdout [,stderr] [,retcode])
        """

        # unused for now
        _ = verbatim_args

        self.setup()

        if args is None:
            args = []

        if env is None:
            env = {}

        env_delta = {}
        env_delta.update(self.env)
        env_delta.update(env)

        if not verbatim_env:
            env_pypath = env_delta.get("PYTHONPATH", os.environ.get("PYTHONPATH"))
            if not env_pypath:
                env_pypath = sys.path
            else:
                env_pypath = env_pypath.split(":")
                for path in sys.path:
                    if path not in env_pypath:
                        env_pypath.append(path)
            # Always ensure that the test tree is searched first for python modules
            if RUNTIME_VARS.CODE_DIR != env_pypath[0]:
                env_pypath.insert(0, RUNTIME_VARS.CODE_DIR)
            if salt.utils.platform.is_windows():
                env_delta["PYTHONPATH"] = ";".join(env_pypath)
            else:
                env_delta["PYTHONPATH"] = ":".join(env_pypath)

        cmd_env = dict(os.environ)
        cmd_env.update(env_delta)

        popen_kwargs = {
            "shell": self.shell,
            "stdout": subprocess.PIPE,
            "env": cmd_env,
        }

        if catch_stderr is True:
            popen_kwargs["stderr"] = subprocess.PIPE

        if not sys.platform.lower().startswith("win"):
            popen_kwargs["close_fds"] = True

            def detach_from_parent_group():
                """
                A utility function that prevents child process from getting parent signals.
                """
                os.setpgrp()

            popen_kwargs["preexec_fn"] = detach_from_parent_group

        if salt.utils.platform.is_windows():
            self.argv = ["python.exe", self.program]
        else:
            self.argv = [self.program]
        self.argv.extend(args)
        log.debug("TestProgram.run: %s Environment %s", self.argv, env_delta)
        process = subprocess.Popen(self.argv, **popen_kwargs)
        self.process = process

        if timeout is not None:
            stop_at = datetime.now() + timedelta(seconds=timeout)
            term_sent = False
            while True:
                process.poll()

                if datetime.now() > stop_at:
                    try:
                        terminate_process(pid=process.pid, kill_children=True)
                        process.wait()
                    except OSError as exc:
                        if exc.errno != errno.ESRCH:
                            raise

                    out = process.stdout.read().splitlines()
                    out.extend(
                        [
                            "Process took more than {} seconds to complete. "
                            "Process Killed!".format(timeout)
                        ]
                    )
                    if catch_stderr:
                        err = process.stderr.read().splitlines()
                        if with_retcode:
                            return out, err, process.returncode
                        else:
                            return out, err
                    if with_retcode:
                        return out, process.returncode
                    else:
                        return out

                if process.returncode is not None:
                    break

        if catch_stderr:
            out, err = process.communicate()
            # Force closing stderr/stdout to release file descriptors
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            # pylint: disable=maybe-no-member
            try:
                if with_retcode:
                    if out is not None and err is not None:
                        if not raw:
                            return (
                                out.splitlines(),
                                err.splitlines(),
                                process.returncode,
                            )
                        else:
                            return out, err, process.returncode
                    return out.splitlines(), [], process.returncode
                else:
                    if out is not None and err is not None:
                        if not raw:
                            return out.splitlines(), err.splitlines()
                        else:
                            return out, err
                    if not raw:
                        return out.splitlines(), []
                    else:
                        return out, []
            finally:
                try:
                    process.terminate()
                except OSError as err:
                    # process already terminated
                    pass
            # pylint: enable=maybe-no-member

        data = process.communicate()
        process.stdout.close()

        try:
            if with_retcode:
                if not raw:
                    return data[0].splitlines(), process.returncode
                else:
                    return data[0], process.returncode
            else:
                if not raw:
                    return data[0].splitlines()
                else:
                    return data[0]
        finally:
            try:
                process.terminate()
            except OSError as err:
                # process already terminated
                pass


@pytest.mark.windows_whitelisted
class TestSaltProgramMeta(TestProgramMeta):
    """
    A Meta-class to set self.script from the class name when it is
    not specifically set by a "script" argument.
    """

    def __new__(mcs, name, bases, attrs):
        if attrs.get("script") is None:
            if "Salt" in name:
                script = "salt-{}".format(name.rsplit("Salt", 1)[-1].lower())
            if script is None:
                raise AttributeError(
                    'Class {}: Unable to set "script" attribute: class name'
                    ' must include "Salt" or "script" must be explicitly set.'.format(
                        name
                    )
                )
            attrs["script"] = script

        config_base = {}
        configs = {}

        for base in bases:
            if "Salt" not in base.__name__:
                continue
            config_base.update(getattr(base, "config_base", {}))
            configs.update(getattr(base, "configs", {}))

        config_base.update(attrs.get("config_base", {}))
        attrs["config_base"] = config_base

        configs.update(attrs.get("configs", {}))
        attrs["configs"] = configs

        return super().__new__(mcs, name, bases, attrs)


@pytest.mark.windows_whitelisted
class TestSaltProgram(TestProgram, ScriptPathMixin, metaclass=TestSaltProgramMeta):
    """
    This is like TestProgram but with some functions to run a salt-specific
    auxiliary program.
    """

    config_types = (dict,)
    config_attrs = {"log_dir", "script_dir"}

    pub_port = 4505
    ret_port = 4506
    for port in [pub_port, ret_port]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            connect = sock.bind(("localhost", port))
        except OSError:
            # these ports are already in use, use different ones
            pub_port = 4606
            ret_port = 4607
            break
        sock.close()

    config_base = {
        "root_dir": "{test_dir}",
        "publish_port": pub_port,
        "ret_port": ret_port,
    }
    configs = {}
    config_dir = os.path.join("etc", "salt")

    log_dir = os.path.join("var", "log", "salt")

    dirtree = [
        "&log_dir",
        "&script_dir",
    ]

    script = ""
    script_dir = "bin"

    @staticmethod
    def config_caster(cfg):
        return salt.utils.yaml.safe_load(cfg)

    def __init__(self, *args, **kwargs):
        if len(args) < 2 and "program" not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs["program"] = self.script
        super().__init__(*args, **kwargs)
        self.program = self.get_script_path(self.script)

    def config_merge(self, base, overrides):
        _base = self.config_cast(copy.deepcopy(base))
        _overrides = self.config_cast(overrides)
        # NOTE: this simple update will not work for deep dictionaries
        _base.update(copy.deepcopy(_overrides))
        return _base

    def config_get(self, config):
        cfg_base = {}
        for key, val in self.config_base.items():
            _val = val
            if val and isinstance(val, str) and val[0] == "&":
                _val = getattr(self, val[1:], None)
                if _val is None:
                    continue
            cfg_base[key] = _val
        if config in self.configs:
            cfg = {}
            for key, val in self.configs.get(config, {}).get("map", {}).items():
                _val = val
                if val and isinstance(val, str) and val[0] == "&":
                    _val = getattr(self, val[1:], None)
                    if _val is None:
                        continue
                cfg[key] = _val
            cfg = self.config_merge(cfg_base, cfg)
        log.debug("Generated config => {}".format(cfg))
        return cfg

    def config_stringify(self, config):
        """Transform the configuration data into a string (suitable to write to a file)"""
        subs = self.config_subs()
        cfg = {}
        for key, val in self.config_get(config).items():
            if isinstance(val, str):
                cfg[key] = val.format(**subs)
            else:
                cfg[key] = val
        return salt.utils.yaml.safe_dump(cfg, default_flow_style=False)

    def run(self, **kwargs):  # pylint: disable=arguments-differ
        if not kwargs.get("verbatim_args"):
            args = kwargs.setdefault("args", [])
            if "-c" not in args and "--config-dir" not in args:
                args.extend(["--config-dir", self.abs_path(self.config_dir)])
        return super().run(**kwargs)


@pytest.mark.windows_whitelisted
class TestProgramSalt(TestSaltProgram):
    """Class to manage salt"""

    configs = {"master": {}}
    script = "salt"


@pytest.mark.windows_whitelisted
class TestDaemon(TestProgram):
    """
    Run one of the standard daemons
    """

    script = None
    pid_file = None
    pid_dir = os.path.join("var", "run")

    dirtree = [
        "&pid_dir",
    ]

    def __init__(self, *args, **kwargs):
        self.script = kwargs.pop("script", self.script)
        self.pid_file = kwargs.pop(
            "pid_file",
            self.pid_file if self.pid_file else "{}.pid".format(self.script),
        )
        self.pid_dir = kwargs.pop("pid_dir", self.pid_dir)
        self._shutdown = False
        if not args and "program" not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs["program"] = self.script
        super().__init__(*args, **kwargs)

    @property
    def pid_path(self):
        """Path to the pid file created by the daemon"""
        return (
            os.path.join(self.pid_dir, self.pid_file)
            if os.path.sep not in self.pid_file
            else self.pid_file
        )

    @property
    def daemon_pid(self):
        """Return the daemon PID"""
        daemon_pid = None
        pid_path = self.abs_path(self.pid_path)
        if salt.utils.process.check_pidfile(pid_path):
            daemon_pid = salt.utils.process.get_pidfile(pid_path)
        return daemon_pid

    def wait_for_daemon_pid(self, timeout=10):
        """Wait up to timeout seconds for the PID file to appear and return the PID"""
        endtime = time.time() + timeout
        while True:
            pid = self.daemon_pid
            if pid:
                return pid
            if endtime < time.time():
                raise TimeoutError(
                    'Timeout waiting for "{}" pid in "{}"'.format(
                        self.name, self.abs_path(self.pid_path)
                    )
                )
            time.sleep(0.2)

    def is_running(self):
        """Is the daemon running?"""
        ret = False
        if not self._shutdown:
            try:
                pid = self.wait_for_daemon_pid()
                ret = psutils.pid_exists(pid)
            except TimeoutError:
                pass
        return ret

    def find_orphans(self, cmdline):
        """Find orphaned processes matching the specified cmdline"""
        ret = []
        cmdline = " ".join(cmdline)
        for proc in psutils.process_iter():
            try:
                for item in proc.cmdline():
                    if cmdline in item:
                        ret.append(proc)
            except psutils.NoSuchProcess:
                # Process exited between when process_iter was invoked and
                # when we tried to invoke this instance's cmdline() func.
                continue
            except psutils.AccessDenied:
                # We might get access denied if not running as root
                if not salt.utils.platform.is_windows():
                    pinfo = proc.as_dict(attrs=["pid", "name", "username"])
                    log.error(
                        "Unable to access process %s, " "running command %s as user %s",
                        pinfo["pid"],
                        pinfo["name"],
                        pinfo["username"],
                    )
                    continue
        return ret

    def shutdown(self, signum=signal.SIGTERM, timeout=10, wait_for_orphans=0):
        """Shutdown a running daemon"""
        if not self._shutdown:
            try:
                pid = self.wait_for_daemon_pid(timeout)
                terminate_process(pid=pid, kill_children=True)
            except TimeoutError:
                pass
        if self.process:
            terminate_process(pid=self.process.pid, kill_children=True)
            self.process.wait()
            if wait_for_orphans:
                # NOTE: The process for finding orphans is greedy, it just
                # looks for processes with the same cmdline which are owned by
                # PID 1.
                orphans = self.find_orphans(self.argv)
                last = time.time()
                while True:
                    if orphans:
                        log.debug("Terminating orphaned child processes: %s", orphans)
                        terminate_process_list(orphans)
                        last = time.time()
                    if (time.time() - last) >= wait_for_orphans:
                        break
                    time.sleep(0.25)
                    orphans = self.find_orphans(self.argv)
            self.process = None
        self._shutdown = True

    def cleanup(self, *args, **kwargs):
        """Remove left-over scaffolding - antithesis of setup()"""

        # Shutdown if not alreadt shutdown
        self.shutdown()
        super().cleanup(*args, **kwargs)


@pytest.mark.windows_whitelisted
class TestSaltDaemon(TestDaemon, TestSaltProgram, metaclass=TestSaltProgramMeta):
    """
    A class to run arbitrary salt daemons (master, minion, syndic, etc.)
    """


@pytest.mark.windows_whitelisted
class TestDaemonSaltMinion(TestSaltDaemon):
    """
    Manager for salt-minion daemon.
    """

    configs = {"minion": {"map": {"id": "{name}"}}}

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault("config_base", {})
        _ = cfgb.setdefault("user", getpass.getuser())
        super().__init__(*args, **kwargs)


@pytest.mark.windows_whitelisted
class TestDaemonSaltApi(TestSaltDaemon):
    """
    Manager for salt-api daemon.
    """


@pytest.mark.windows_whitelisted
class TestDaemonSaltSyndic(TestSaltDaemon):
    """
    Manager for salt-syndic daemon.
    """

    configs = {
        "master": {"map": {"syndic_master": "localhost"}},
        "minion": {"map": {"id": "{name}"}},
    }

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault("config_base", {})
        _ = cfgb.setdefault("user", getpass.getuser())
        super().__init__(*args, **kwargs)


@pytest.mark.windows_whitelisted
class TestProgramCase(TestCase):
    """
    Utilities for unit tests that use TestProgram()
    """

    def setUp(self):
        # Setup for scripts
        if not getattr(self, "_test_dir", None):
            self._test_dir = tempfile.mkdtemp(prefix="salt-testdaemon-")
        super().setUp()

    def tearDown(self):
        # shutdown for scripts
        if self._test_dir and os.path.sep == self._test_dir[0]:
            shutil.rmtree(self._test_dir)
            self._test_dir = None
        super().tearDown()

    def assert_exit_status(
        self, status, ex_status, message=None, stdout=None, stderr=None
    ):
        """
        Helper function to verify exit status and emit failure information.
        """

        ex_val = getattr(exitcodes, ex_status)
        _message = "" if not message else " ({})".format(message)
        _stdout = "" if not stdout else "\nstdout: {}".format(stdout)
        _stderr = "" if not stderr else "\nstderr: {}".format(stderr)
        self.assertEqual(
            status,
            ex_val,
            "Exit status was {}, must be {} (salt.default.exitcodes.{}){}{}{}".format(
                status, ex_val, ex_status, _message, _stdout, _stderr,
            ),
        )
