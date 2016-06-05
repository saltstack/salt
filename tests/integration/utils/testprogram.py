# -*- coding: utf-8 -*-
'''
Classes for starting/stopping/status salt daemons, auxiliary
scripts, generic commands.
'''

import atexit
import copy
from datetime import datetime, timedelta
import errno
import getpass
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import yaml

import salt.ext.six as six
import salt.utils.process
import salt.utils.psutil_compat as psutils
from salt.defaults import exitcodes

from salttesting import TestCase

import integration

LOG = logging.getLogger(__name__)


if 'TimeoutError' not in __builtins__:
    class TimeoutError(OSError):
        '''Compatibility exception with python3'''
        pass
    __builtins__['TimeoutError'] = TimeoutError


# pylint: disable=too-many-instance-attributes
class TestProgram(object):
    '''
    Set up an arbitrary executable to run.
    '''

    def __init__(self, program=None, name=None, env=None, shell=False, parent_dir=None, clean_on_exit=True):
        self.program = program or getattr(self, 'program', None)
        self.name = name or getattr(self, 'name', None)
        self.env = env or {}
        if 'PYTHONPATH' not in self.env:
            self.env['PYTHONPATH'] = ':'.join(sys.path)
        self.shell = shell
        self._parent_dir = parent_dir or None
        self.clean_on_exit = clean_on_exit

        if not self.name:
            if not self.program:
                raise ValueError('"{0}" object must specify "program" parameter'.format(self.__class__.__name__))
            self.name = os.path.basename(self.program)

        self.process = None
        self.created_parent_dir = False
        self._setup_done = False

        # Register the exit clean-up before making anything needing clean-up
        atexit.register(self.cleanup)

    def __enter__(self):
        pass

    def __exit__(self, typ, value, traceback):
        pass

    @property
    def start_pid(self):
        '''PID of the called script prior to deamonizing.'''
        return self.process.pid if self.process else None

    @property
    def parent_dir(self):
        '''Directory that contains everything generated for running scripts - possibly for multiple scripts.'''
        if self._parent_dir is None:
            self.created_parent_dir = True
            self._parent_dir = tempfile.mkdtemp(prefix='salt-testdaemon-XXXX')
        else:
            self._parent_dir = os.path.abspath(os.path.normpath(self._parent_dir))
            if not os.path.exists(self._parent_dir):
                self.created_parent_dir = True
                os.makedirs(self._parent_dir)
            elif not os.path.isdir(self._parent_dir):
                raise ValueError('Parent path "{0}" exists but is not a directory'.format(self._parent_dir))
        return self._parent_dir

    def setup(self, *args, **kwargs):
        '''Create any scaffolding for run-time'''
        pass

    def cleanup(self, *args, **kwargs):
        ''' Clean out scaffolding of setup() and any run-time generated files.'''
        # Unused for now
        _ = (args, kwargs)

        if self.process:
            try:
                self.process.kill()
                self.process.wait()
            except OSError:
                pass
        if self.created_parent_dir and os.path.exists(self.parent_dir):
            shutil.rmtree(self.parent_dir)

    def run(
            self,
            args=None,
            catch_stderr=False,
            with_retcode=False,
            timeout=None,
            raw=False,
    ):
        '''
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

        :param shell: A boolean of whether the command is processed by the
            shell or invoked with execv.

        :return list: (stdout [,stderr] [,retcode])
        '''

        if not self._setup_done:
            self.setup()
            self._setup_done = True

        if args is None:
            args = []

        cmd_env = dict(os.environ)
        cmd_env.update(self.env)

        popen_kwargs = {
            'shell': self.shell,
            'stdout': subprocess.PIPE,
            'env': cmd_env,
        }

        if catch_stderr is True:
            popen_kwargs['stderr'] = subprocess.PIPE

        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True

            def detach_from_parent_group():
                '''
                A utility function that prevents child process from getting parent signals.
                '''
                os.setpgrp()

            popen_kwargs['preexec_fn'] = detach_from_parent_group

        elif sys.platform.lower().startswith('win') and timeout is not None:
            raise RuntimeError('Timeout is not supported under windows')

        argv = [self.program]
        argv.extend(args)
        LOG.debug('TestProgram.run: {0} Environment {1}'.format(argv, cmd_env))
        process = subprocess.Popen(argv, **popen_kwargs)
        self.process = process

        if timeout is not None:
            stop_at = datetime.now() + timedelta(seconds=timeout)
            term_sent = False
            while True:
                process.poll()

                if datetime.now() > stop_at:
                    if term_sent is False:
                        # Kill the process group since sending the term signal
                        # would only terminate the shell, not the command
                        # executed in the shell
                        os.killpg(os.getpgid(process.pid), signal.SIGINT)
                        term_sent = True
                        continue

                    try:
                        # As a last resort, kill the process group
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait()
                    except OSError as exc:
                        if exc.errno != errno.ESRCH:
                            raise

                    out = process.stdout.read().splitlines()
                    out.extend([
                        'Process took more than {0} seconds to complete. '
                        'Process Killed!'.format(timeout)
                    ])
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
            if sys.version_info < (2, 7):
                # On python 2.6, the subprocess'es communicate() method uses
                # select which, is limited by the OS to 1024 file descriptors
                # We need more available descriptors to run the tests which
                # need the stderr output.
                # So instead of .communicate() we wait for the process to
                # finish, but, as the python docs state "This will deadlock
                # when using stdout=PIPE and/or stderr=PIPE and the child
                # process generates enough output to a pipe such that it
                # blocks waiting for the OS pipe buffer to accept more data.
                # Use communicate() to avoid that." <- a catch, catch situation
                #
                # Use this work around were it's needed only, python 2.6
                process.wait()
                out = process.stdout.read()
                err = process.stderr.read()
            else:
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
                            return out.splitlines(), err.splitlines(), process.returncode
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


class TestSaltProgramMeta(type):
    '''
    A Meta-class to set self.script from the class name when it is
    not specifically set by a "script" argument.
    '''
    def __new__(mcs, name, bases, attrs):
        if attrs.get('script') is None:
            if 'Salt' in name:
                script = 'salt-{0}'.format(name.rsplit('Salt', 1)[-1].lower())
            if script is None:
                raise AttributeError(
                    'Class {0}: Unable to set "script" attribute: class name'
                    ' must include "Salt" or "script" must be explicitly set.'.format(name)
                )
            attrs['script'] = script

        return super(TestSaltProgramMeta, mcs).__new__(mcs, name, bases, attrs)


class TestSaltProgram(TestProgram):
    '''
    This is like TestProgram but with some functions to run a salt-specific
    auxiliary program.
    '''

    __metaclass__ = TestSaltProgramMeta

    script = ''

    def __init__(self, *args, **kwargs):
        if len(args) < 2 and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        super(TestSaltProgram, self).__init__(*args, **kwargs)
        self.program = self.script_path

    @property
    def script_dir(self):
        '''The directory where the script is written.'''
        return os.path.join(self.parent_dir, 'bin')

    @property
    def script_path(self):
        '''Full path of the run-time script.'''
        return os.path.join(self.script_dir, self.script)

    def setup(self, *args, **kwargs):
        super(TestSaltProgram, self).setup(*args, **kwargs)
        self.install_script()

    def install_script(self):
        '''Generate the script file that calls python objects and libraries.'''
        if not os.path.exists(self.script_dir):
            os.makedirs(self.script_dir)

        lines = []
        script_source = os.path.join(integration.CODE_DIR, 'scripts', self.script)
        with open(script_source, 'r') as sso:
            lines.extend(sso.readlines())
        if lines[0].startswith('#!'):
            lines.pop(0)
        lines.insert(0, '#!{0}\n'.format(sys.executable))

        with open(self.script_path, 'w') as sdo:
            sdo.write(''.join(lines))
            sdo.flush()

        os.chmod(self.script_path, 0755)


class TestProgramSaltCall(TestSaltProgram):
    '''Class to manage salt-call'''
    pass


class TestDaemon(TestProgram):
    '''
    Run one of the standard daemons
    '''

    script = None
    empty_config = ''
    pid_file = None
    config_file = ''

    config_types = (six.string_types,)

    dirtree = []

    def __init__(self, *args, **kwargs):
        self._config = kwargs.pop('config', copy.copy(self.empty_config))
        self.script = kwargs.pop('script', self.script)
        self.pid_file = kwargs.pop('pid_file', '{0}.pid'.format(self.script))
        self.config_file = kwargs.pop('config_file', self.config_file)
        self._shutdown = False
        if not args and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        super(TestDaemon, self).__init__(*args, **kwargs)

    @property
    def root_dir(self):
        '''Directory that will contains all of the static and dynamic files for the daemon'''
        return os.path.join(self.parent_dir, self.name)

    @property
    def pid_path(self):
        '''Full path of the PID file'''
        return os.path.join(self.root_dir, 'var', 'run', self.pid_file)

    @property
    def daemon_pid(self):
        '''Return the daemon PID'''
        return (
            salt.utils.process.get_pidfile(self.pid_path)
            if salt.utils.process.check_pidfile(self.pid_path)
            else None
        )

    def wait_for_daemon_pid(self, timeout=0):
        '''Wait up to timeout seconds for the PID file to appear and return the PID'''
        endtime = time.time() + timeout
        while True:
            pid = self.daemon_pid
            if pid:
                return pid
            if endtime < time.time():
                raise TimeoutError('Timeout waiting for "{0}" pid in "{1}"'.format(self.name, self.pid_path))
            time.sleep(0.2)

    def is_running(self):
        '''Is the daemon running?'''
        ret = False
        if not self._shutdown:
            try:
                pid = self.wait_for_daemon_pid()
                ret = psutils.pid_exists(pid)
            except TimeoutError:
                pass
        return ret

    def shutdown(self, signum=signal.SIGTERM, timeout=10):
        '''Shutdown a running daemon'''
        if not self._shutdown and self.process and self.process.returncode == exitcodes.EX_OK:
            pid = self.wait_for_daemon_pid()
            future = datetime.now() + timedelta(seconds=timeout)
            while True:
                if datetime.now() > future:
                    raise TimeoutError('Timeout waiting for "{0}" pid'.format(pid))
                if not salt.utils.process.os_is_running(pid):
                    break
                try:
                    os.kill(pid, signum)
                except OSError as err:
                    if errno.ESRCH != err.errno:
                        break
                    raise
                time.sleep(0.1)
            self._shutdown = True

    @property
    def config_dir(self):
        '''Directory of the config file'''
        return os.path.join(self.root_dir, 'etc', 'salt')

    def setup(self, *args, **kwargs):
        '''Perform any necessary setup to be ready to run'''
        super(TestDaemon, self).setup(*args, **kwargs)
        self.config_write()
        self.make_dirtree()

    def cleanup(self, *args, **kwargs):
        '''Remove left-over scaffolding - antithesis of setup()'''
        self.shutdown()
        if os.path.exists(self.root_dir):
            shutil.rmtree(self.root_dir)
        super(TestDaemon, self).cleanup(*args, **kwargs)

    @property
    def config_path(self):
        '''The full path of the configuration file.'''
        return os.path.join(self.config_dir, self.config_file)

    def config_write(self):
        '''Write out the config to a file'''
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        with open(self.config_path, 'w') as cfo:
            cfg = self.config_stringify()
            LOG.debug('Writing configuration for {0} to {1}:\n{2}'.format(
                self.name, self.config_path, cfg
            ))
            cfo.write(cfg)
            cfo.flush()

    def make_dirtree(self):
        '''Create directory structure.'''
        for branch in self.dirtree:
            path = os.path.join(self.root_dir, branch)
            if not os.path.exists(path):
                os.makedirs(path)

    def config_type(self, config):
        '''Check if a configuration is an acceptable type.'''
        return isinstance(config, self.config_types)

    def config_cast(self, config):
        '''Cast a configuration to the internal expected type.'''
        if not isinstance(config, six.string_types):
            config = str(config)
        return config

    def config_stringify(self):
        '''Marshall the configuration to a string'''
        return self.config

    def config_merge(self, base, overrides):
        '''Merge two configuration hunks'''
        base = self.config_cast(base)
        overrides = self.config_cast(overrides)
        return ''.join([base, overrides])

    @property
    def config(self):
        '''Get the configuration'''
        return self._config

    @config.setter
    def config(self, val):
        '''Set the configuration'''
        if val is None:
            val = ''
        self._config = self.config_cast(val)


class TestSaltDaemonMeta(TestSaltProgramMeta, type):
    '''
    A meta-class to stack all inherited config_attrs from the base classes.
    '''
    def __new__(mcs, name, bases, attrs):
        config_attrs = {}
        dirtree = set()
        for base in bases:
            config_attrs.update(getattr(base, 'config_attrs', {}))
            dirtree.update(getattr(base, 'dirtree', []))
        config_attrs.update(attrs.get('config_attrs', {}))
        dirtree.update(attrs.get('dirtree', []))
        attrs['config_attrs'] = config_attrs
        attrs['dirtree'] = dirtree
        return super(TestSaltDaemonMeta, mcs).__new__(mcs, name, bases, attrs)


class TestSaltDaemon(TestDaemon, TestSaltProgram):
    '''
    A class to run arbitrary salt daemons (master, minion, syndic, etc.)
    '''

    __metaclass__ = TestSaltDaemonMeta

    config_types = (dict,)
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
    }
    script = ''
    empty_config = {}

    dirtree = [
        'var/log/salt',
    ]

    def __init__(self, *args, **kwargs):
        super(TestSaltDaemon, self).__init__(*args, **kwargs)
        path = self.env.get('PATH', os.getenv('PATH'))
        self.env['PATH'] = ':'.join([self.script_dir, path])

    def config_cast(self, config):
        if isinstance(config, six.string_types):
            config = yaml.safe_load(config)
        return config

    def config_merge(self, base, overrides):
        _base = self.config_cast(copy.deepcopy(base))
        _overrides = self.config_cast(overrides)
        # NOTE: this simple update will not work for deep dictionaries
        _base.update(copy.deepcopy(_overrides))
        return _base

    @property
    def config(self):
        attr_vals = dict([(k, getattr(self, v if v else k)) for k, v in self.config_attrs.items()])
        merged = self.config_merge(self._config, attr_vals)
        return merged

    def config_stringify(self):
        return yaml.safe_dump(self.config, default_flow_style=False)

    def run(self, **kwargs):
        args = kwargs.get('args', [])
        if '-c' not in args and '--config-dir' not in args:
            args.extend(['--config-dir', self.config_dir])
        kwargs['args'] = args
        return super(TestSaltDaemon, self).run(**kwargs)


class TestDaemonSaltMaster(TestSaltDaemon):
    '''
    Manager for salt-master daemon.
    '''

    config_file = 'master'

    def __init__(self, *args, **kwargs):
        cfg = kwargs.setdefault('config', {})
        _ = cfg.setdefault('user', getpass.getuser())
        super(TestDaemonSaltMaster, self).__init__(*args, **kwargs)


class TestDaemonSaltMinion(TestSaltDaemon):
    '''
    Manager for salt-minion daemon.
    '''

    config_attrs = {
        'id': 'name',
    }
    config_file = 'minion'

    def __init__(self, *args, **kwargs):
        cfg = kwargs.setdefault('config', {})
        _ = cfg.setdefault('user', getpass.getuser())
        super(TestDaemonSaltMinion, self).__init__(*args, **kwargs)


class TestDaemonSaltApi(TestSaltDaemon):
    '''
    Manager for salt-api daemon.
    '''
    pass


class TestDaemonSaltSyndic(TestSaltDaemon):
    '''
    Manager for salt-syndic daemon.
    '''
    pass


class TestDaemonSaltProxy(TestSaltDaemon):
    '''
    Manager for salt-proxy daemon.
    '''

    config_file = 'proxy'

    def __init__(self, *args, **kwargs):
        cfg = kwargs.setdefault('config', {})
        _ = cfg.setdefault('user', getpass.getuser())
        super(TestDaemonSaltProxy, self).__init__(*args, **kwargs)


class TestProgramCase(TestCase):
    '''
    Utilities for unit tests that use TestProgram()
    '''

    def setUp(self):
        # Setup for scripts
        if not getattr(self, '_test_dir', None):
            self._test_dir = tempfile.mkdtemp(prefix='salt-testdaemon-')
        super(TestProgramCase, self).setUp()

    def tearDown(self):
        # shutdown for scripts
        if self._test_dir and os.path.sep == self._test_dir[0]:
            shutil.rmtree(self._test_dir)
            self._test_dir = None
        super(TestProgramCase, self).tearDown()

    def assert_exit_status(self, status, ex_status, message=None, stdout=None, stderr=None):
        '''
        Helper function to verify exit status and emit failure information.
        '''

        ex_val = getattr(exitcodes, ex_status)
        _message = '' if not message else ' ({0})'.format(message)
        _stdout = '' if not stdout else '\nstdout: {0}'.format('\nstdout: '.join(stdout))
        _stderr = '' if not stderr else '\nstderr: {0}'.format('\nstderr: '.join(stderr))
        self.assertEqual(
            status,
            ex_val,
            'Exit status was {0}, must be {1} (salt.default.exitcodes.{2}){3}{4}{5}'.format(
                status,
                ex_val,
                ex_status,
                _message,
                _stderr,
                _stderr,
            )
        )
