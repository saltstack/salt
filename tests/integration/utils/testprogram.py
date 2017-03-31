# -*- coding: utf-8 -*-
'''
Classes for starting/stopping/status salt daemons, auxiliary
scripts, generic commands.
'''

from __future__ import absolute_import
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

import salt.utils.process
import salt.utils.psutil_compat as psutils
import salt.defaults.exitcodes as exitcodes
import salt.ext.six as six

from tests.support.unit import TestCase

import tests.integration as integration
from tests.support.processes import terminate_process

log = logging.getLogger(__name__)


if 'TimeoutError' not in __builtins__:
    class TimeoutError(OSError):
        '''Compatibility exception with python3'''
        pass
    __builtins__['TimeoutError'] = TimeoutError


class TestProgramMeta(type):
    '''
    Stack all inherited config_attrs and dirtree dirs from the base classes.
    '''
    def __new__(mcs, name, bases, attrs):
        config_vals = {}
        config_attrs = set()
        dirtree = set()

        for base in bases:
            config_vals.update(getattr(base, 'config_vals', {}))
            config_attrs.update(getattr(base, 'config_attrs', {}))
            dirtree.update(getattr(base, 'dirtree', []))

        config_vals.update(attrs.get('config_vals', {}))
        attrs['config_vals'] = config_vals

        config_attrs.update(attrs.get('config_attrs', {}))
        attrs['config_attrs'] = config_attrs

        dirtree.update(attrs.get('dirtree', []))
        attrs['dirtree'] = dirtree

        return super(TestProgramMeta, mcs).__new__(mcs, name, bases, attrs)


# pylint: disable=too-many-instance-attributes
class TestProgram(six.with_metaclass(TestProgramMeta, object)):
    '''
    Set up an arbitrary executable to run.

    :attribute dirtree: An iterable of directories to be created
    '''

    empty_config = ''
    config_file = ''

    config_attrs = set([
        'name',
        'test_dir',
        'config_dirs',
    ])
    config_vals = {
    }
    config_base = ''
    config_dir = os.path.join('etc')
    configs = {}
    config_types = (str, six.string_types,)

    dirtree = [
        '&config_dirs',
    ]

    @staticmethod
    def config_caster(cfg):
        return str(cfg)

    def __init__(self, program=None, name=None, env=None, shell=False, parent_dir=None, clean_on_exit=True, **kwargs):
        self.program = program or getattr(self, 'program', None)
        self.name = name or getattr(self, 'name', '')
        self.env = env or {}
        self.shell = shell
        self._parent_dir = parent_dir or None
        self.clean_on_exit = clean_on_exit
        self._root_dir = kwargs.pop('root_dir', self.name)
        self.config_dir = kwargs.pop('config_dir', copy.copy(self.config_dir))

        config_attrs = copy.copy(self.config_attrs)
        config_attrs.update(kwargs.pop('config_attrs', set()))
        self.config_attrs = config_attrs

        config_vals = copy.copy(self.config_vals)
        config_vals.update(kwargs.pop('config_vals', {}))
        self.config_vals = config_vals

        config_base = copy.deepcopy(self.config_base)
        config_base = self.config_merge(config_base, kwargs.pop('config_base', self.config_types[0]()))
        self.config_base = config_base

        configs = copy.deepcopy(self.configs)
        for cname, cinfo in kwargs.pop('configs', {}).items():
            target = configs.setdefault(cname, {})
            if 'path' in cinfo:
                target['path'] = cinfo['path']
            if 'map' in cinfo:
                target_map = target.setdefault('map', self.config_types[0]())
                target_map = self.config_merge(target_map, cinfo['map'])
                target['map'] = target_map
        self.configs = configs

        if not self.name:
            if not self.program:
                raise ValueError('"{0}" object must specify "program" parameter'.format(self.__class__.__name__))
            self.name = os.path.basename(self.program)

        self.process = None
        self.created_parent_dir = False
        self._setup_done = False

        dirtree = set(self.dirtree)
        dirtree.update(kwargs.pop('dirtree', []))
        self.dirtree = dirtree

        # Register the exit clean-up before making anything needing clean-up
        atexit.register(self.cleanup)

    def __enter__(self):
        pass

    def __exit__(self, typ, value, traceback):
        pass

    @property
    def test_dir(self):
        '''Directory that will contains all of the static and dynamic files for the daemon'''
        return os.path.join(self.parent_dir, self._root_dir)

    def config_file_get(self, config):
        '''Get the filename (viz. path) to the configuration file'''
        cfgf = self.configs[config].get('path')
        if cfgf:
            cfgf.format(**self.config_subs())
        else:
            cfgf = os.path.join(self.config_dir, config)
        return cfgf

    def config_dir_get(self, config):
        '''Get the parent directory for the configuration file'''
        return os.path.dirname(self.config_file_get(config))

    @property
    def config_dirs(self):
        '''Return a list of configuration directories'''
        cdirs = [self.config_dir_get(config) for config in self.configs.keys()]
        return cdirs

    def abs_path(self, path):
        '''Absolute path of file including the test_dir'''
        return os.path.join(self.test_dir, path)

    @property
    def start_pid(self):
        '''PID of the called script prior to deamonizing.'''
        return self.process.pid if self.process else None

    @property
    def parent_dir(self):
        '''
        Directory that contains everything generated for running scripts - possibly
        for multiple scripts.
        '''
        if self._parent_dir is None:
            self.created_parent_dir = True
            self._parent_dir = tempfile.mkdtemp(prefix='salt-testdaemon-')
        else:
            self._parent_dir = os.path.abspath(os.path.normpath(self._parent_dir))
            if not os.path.exists(self._parent_dir):
                self.created_parent_dir = True
                os.makedirs(self._parent_dir)
            elif not os.path.isdir(self._parent_dir):
                raise ValueError('Parent path "{0}" exists but is not a directory'.format(self._parent_dir))
        return self._parent_dir

    def config_write(self, config):
        '''Write out the config to a file'''
        if not config:
            return
        cpath = self.abs_path(self.config_file_get(config))
        with open(cpath, 'w') as cfo:
            cfg = self.config_stringify(config)
            log.debug('Writing configuration for {0} to {1}:\n{2}'.format(self.name, cpath, cfg))
            cfo.write(cfg)
            cfo.flush()

    def configs_write(self):
        '''Write all configuration files'''
        for config in self.configs:
            self.config_write(config)

    def config_type(self, config):
        '''Check if a configuration is an acceptable type.'''
        return isinstance(config, self.config_types)

    def config_cast(self, config):
        '''Cast a configuration to the internal expected type.'''
        if not self.config_type(config):
            config = self.config_caster(config)
        return config

    def config_subs(self):
        '''Get the substitution values for use to generate the config'''
        subs = dict([(attr, getattr(self, attr, None)) for attr in self.config_attrs])
        for key, val in self.config_vals.items():
            subs[key] = val.format(**subs)
        return subs

    def config_stringify(self, config):
        '''Get the configuration as a string'''
        cfg = self.config_get(config)
        cfg.format(**self.config_subs())
        return cfg

    def config_merge(self, base, overrides):
        '''Merge two configuration hunks'''
        base = self.config_cast(base)
        overrides = self.config_cast(overrides)
        return ''.join([base, overrides])

    def config_get(self, config):
        '''Get the configuration data'''
        return self.configs[config]

    def config_set(self, config, val):
        '''Set the configuration data'''
        self.configs[config] = val

    def make_dirtree(self):
        '''Create directory structure.'''
        subdirs = []
        for branch in self.dirtree:
            log.debug('checking dirtree: {0}'.format(branch))
            if not branch:
                continue
            if isinstance(branch, six.string_types) and branch[0] == '&':
                log.debug('Looking up dirtree branch "{0}"'.format(branch))
                try:
                    dirattr = getattr(self, branch[1:], None)
                    log.debug('dirtree "{0}" => "{1}"'.format(branch, dirattr))
                except AttributeError:
                    raise ValueError(
                        'Unable to find dirtree attribute "{0}" on object "{1}.name = {2}: {3}"'.format(
                            branch, self.__class__.__name__, self.name, dir(self),
                        )
                    )

                if not dirattr:
                    continue

                if isinstance(dirattr, six.string_types):
                    subdirs.append(dirattr)
                elif hasattr(dirattr, '__iter__'):
                    subdirs.extend(dirattr)
                else:
                    raise TypeError("Branch type of {0} in dirtree is unhandled".format(branch))
            elif isinstance(branch, six.string_types):
                subdirs.append(branch)
            else:
                raise TypeError("Branch type of {0} in dirtree is unhandled".format(branch))

        for subdir in subdirs:
            path = self.abs_path(subdir)
            if not os.path.exists(path):
                log.debug('make_dirtree: {0}'.format(path))
                os.makedirs(path)

    def setup(self, *args, **kwargs):
        '''Create any scaffolding for run-time'''

        # unused
        _ = args, kwargs

        if not self._setup_done:
            self.make_dirtree()
            self.configs_write()
            self._setup_done = True

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

        :param verbatim_args: A boolean whether to automatically add inferred arguments.

        :param verbatim_env: A boolean whether to automatically add inferred
            environment values.

        :return list: (stdout [,stderr] [,retcode])
        '''

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
            env_pypath = env_delta.get('PYTHONPATH', os.environ.get('PYTHONPATH'))
            if not env_pypath:
                env_pypath = sys.path
            else:
                env_pypath = env_pypath.split(':')
                for path in sys.path:
                    if path not in env_pypath:
                        env_pypath.append(path)
            # Always ensure that the test tree is searched first for python modules
            if integration.CODE_DIR != env_pypath[0]:
                env_pypath.insert(0, integration.CODE_DIR)
            env_delta['PYTHONPATH'] = ':'.join(env_pypath)

        cmd_env = dict(os.environ)
        cmd_env.update(env_delta)

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
        log.debug('TestProgram.run: {0} Environment {1}'.format(argv, env_delta))
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


class TestSaltProgramMeta(TestProgramMeta):
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

        config_base = {}
        configs = {}

        for base in bases:
            if 'Salt' not in base.__name__:
                continue
            config_base.update(getattr(base, 'config_base', {}))
            configs.update(getattr(base, 'configs', {}))

        config_base.update(attrs.get('config_base', {}))
        attrs['config_base'] = config_base

        configs.update(attrs.get('configs', {}))
        attrs['configs'] = configs

        return super(TestSaltProgramMeta, mcs).__new__(mcs, name, bases, attrs)


class TestSaltProgram(six.with_metaclass(TestSaltProgramMeta, TestProgram)):
    '''
    This is like TestProgram but with some functions to run a salt-specific
    auxiliary program.
    '''
    config_types = (dict,)
    config_attrs = set([
        'log_dir',
        'script_dir',
    ])
    config_base = {
        'root_dir': '{test_dir}',
    }
    configs = {}
    config_dir = os.path.join('etc', 'salt')

    log_dir = os.path.join('var', 'log', 'salt')

    dirtree = [
        '&log_dir',
        '&script_dir',
    ]

    script = ''
    script_dir = 'bin'

    @staticmethod
    def config_caster(cfg):
        return yaml.safe_load(cfg)

    def __init__(self, *args, **kwargs):
        if len(args) < 2 and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        super(TestSaltProgram, self).__init__(*args, **kwargs)
        self.program = self.abs_path(os.path.join(self.script_dir, self.script))
        path = self.env.get('PATH', os.getenv('PATH'))
        self.env['PATH'] = ':'.join([self.abs_path(self.script_dir), path])

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
            if val and isinstance(val, six.string_types) and val[0] == '&':
                _val = getattr(self, val[1:], None)
                if _val is None:
                    continue
            cfg_base[key] = _val
        if config in self.configs:
            cfg = {}
            for key, val in self.configs.get(config, {}).get('map', {}).items():
                _val = val
                if val and isinstance(val, six.string_types) and val[0] == '&':
                    _val = getattr(self, val[1:], None)
                    if _val is None:
                        continue
                cfg[key] = _val
            cfg = self.config_merge(cfg_base, cfg)
        log.debug('Generated config => {0}'.format(cfg))
        return cfg

    def config_stringify(self, config):
        '''Transform the configuration data into a string (suitable to write to a file)'''
        subs = self.config_subs()
        cfg = {}
        for key, val in self.config_get(config).items():
            if isinstance(val, six.string_types):
                cfg[key] = val.format(**subs)
            else:
                cfg[key] = val
        scfg = yaml.safe_dump(cfg, default_flow_style=False)
        return scfg

    def setup(self, *args, **kwargs):
        super(TestSaltProgram, self).setup(*args, **kwargs)
        self.install_script()

    def install_script(self):
        '''Generate the script file that calls python objects and libraries.'''
        lines = []
        script_source = os.path.join(integration.CODE_DIR, 'scripts', self.script)
        with open(script_source, 'r') as sso:
            lines.extend(sso.readlines())
        if lines[0].startswith('#!'):
            lines.pop(0)
        lines.insert(0, '#!{0}\n'.format(sys.executable))

        script_path = self.abs_path(os.path.join(self.script_dir, self.script))
        log.debug('Installing "{0}" to "{1}"'.format(script_source, script_path))
        with open(script_path, 'w') as sdo:
            sdo.write(''.join(lines))
            sdo.flush()

        os.chmod(script_path, 0o755)

    def run(self, **kwargs):
        if not kwargs.get('verbatim_args'):
            args = kwargs.setdefault('args', [])
            if '-c' not in args and '--config-dir' not in args:
                args.extend(['--config-dir', self.abs_path(self.config_dir)])
        return super(TestSaltProgram, self).run(**kwargs)


class TestProgramSalt(TestSaltProgram):
    '''Class to manage salt'''

    configs = {'master': {}}
    script = 'salt'


class TestProgramSaltCall(TestSaltProgram):
    '''Class to manage salt-call'''

    configs = {'minion': {'map': {'id': '{name}'}}}


class TestProgramSaltRun(TestSaltProgram):
    '''Class to manage salt-run'''

    configs = {'master': {}}

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault('config_base', {})
        _ = cfgb.setdefault('user', getpass.getuser())
        super(TestProgramSaltRun, self).__init__(*args, **kwargs)


class TestDaemon(TestProgram):
    '''
    Run one of the standard daemons
    '''

    script = None
    pid_file = None
    pid_dir = os.path.join('var', 'run')

    dirtree = [
        '&pid_dir',
    ]

    def __init__(self, *args, **kwargs):
        self.script = kwargs.pop('script', self.script)
        self.pid_file = kwargs.pop('pid_file', self.pid_file if self.pid_file else '{0}.pid'.format(self.script))
        self.pid_dir = kwargs.pop('pid_dir', self.pid_dir)
        self._shutdown = False
        if not args and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        super(TestDaemon, self).__init__(*args, **kwargs)

    @property
    def pid_path(self):
        '''Path to the pid file created by the daemon'''
        return os.path.join(self.pid_dir, self.pid_file) if os.path.sep not in self.pid_file else self.pid_file

    @property
    def daemon_pid(self):
        '''Return the daemon PID'''
        daemon_pid = None
        pid_path = self.abs_path(self.pid_path)
        if salt.utils.process.check_pidfile(pid_path):
            daemon_pid = salt.utils.process.get_pidfile(pid_path)
        return daemon_pid

    def wait_for_daemon_pid(self, timeout=10):
        '''Wait up to timeout seconds for the PID file to appear and return the PID'''
        endtime = time.time() + timeout
        while True:
            pid = self.daemon_pid
            if pid:
                return pid
            if endtime < time.time():
                raise TimeoutError('Timeout waiting for "{0}" pid in "{1}"'.format(
                    self.name, self.abs_path(self.pid_path)
                ))
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
        if not self._shutdown:
            try:
                pid = self.wait_for_daemon_pid(timeout)
                terminate_process(pid=pid)
            except TimeoutError:
                pass
        if self.process:
            terminate_process(pid=self.process.pid)
            self.process.wait()
            self.process = None
        self._shutdown = True

    def cleanup(self, *args, **kwargs):
        '''Remove left-over scaffolding - antithesis of setup()'''

        # Shutdown if not alreadt shutdown
        self.shutdown()
        super(TestDaemon, self).cleanup(*args, **kwargs)


class TestSaltDaemon(six.with_metaclass(TestSaltProgramMeta, TestDaemon, TestSaltProgram)):
    '''
    A class to run arbitrary salt daemons (master, minion, syndic, etc.)
    '''
    pass


class TestDaemonSaltMaster(TestSaltDaemon):
    '''
    Manager for salt-master daemon.
    '''

    configs = {'master': {}}

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault('config_base', {})
        _ = cfgb.setdefault('user', getpass.getuser())
        super(TestDaemonSaltMaster, self).__init__(*args, **kwargs)


class TestDaemonSaltMinion(TestSaltDaemon):
    '''
    Manager for salt-minion daemon.
    '''

    configs = {'minion': {'map': {'id': '{name}'}}}

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault('config_base', {})
        _ = cfgb.setdefault('user', getpass.getuser())
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

    configs = {
        'master': {'map': {'syndic_master': 'localhost'}},
        'minion': {'map': {'id': '{name}'}},
    }

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault('config_base', {})
        _ = cfgb.setdefault('user', getpass.getuser())
        super(TestDaemonSaltSyndic, self).__init__(*args, **kwargs)


class TestDaemonSaltProxy(TestSaltDaemon):
    '''
    Manager for salt-proxy daemon.
    '''

    pid_file = 'salt-minion.pid'
    configs = {'proxy': {}}

    def __init__(self, *args, **kwargs):
        cfgb = kwargs.setdefault('config_base', {})
        _ = cfgb.setdefault('user', getpass.getuser())
        super(TestDaemonSaltProxy, self).__init__(*args, **kwargs)

    def run(self, **kwargs):
        if not kwargs.get('verbatim_args'):
            args = kwargs.setdefault('args', [])
            if '--proxyid' not in args:
                args.extend(['--proxyid', self.name])
        return super(TestDaemonSaltProxy, self).run(**kwargs)


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
        _stdout = '' if not stdout else '\nstdout: {0}'.format(stdout)
        _stderr = '' if not stderr else '\nstderr: {0}'.format(stderr)
        self.assertEqual(
            status,
            ex_val,
            'Exit status was {0}, must be {1} (salt.default.exitcodes.{2}){3}{4}{5}'.format(
                status,
                ex_val,
                ex_status,
                _message,
                _stdout,
                _stderr,
            )
        )
