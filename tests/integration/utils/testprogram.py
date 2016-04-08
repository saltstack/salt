import atexit
import copy
from datetime import datetime, timedelta
import logging
import os
import shutil
import signal
import string
import subprocess
import sys
import tempfile
import time

import yaml

import salt.ext.six as six

import integration

LOG = logging.getLogger(__name__)


class TestProgram(object):
    '''
    Set up a program to run.
    '''

    #def __init__(self, name, program=None, env=None, shell=False, parent_dir=None, clean_on_exit=True, *args, **kwargs):
    def __init__(self, *args, **kwargs):
        args = list(args)
        LOG.warning('TLH: TestProgram(*args={0}, **kwargs={1})'.format(args, kwargs))
        if args:
            self.name = args.pop(0)
            if args:
                self.program = args.pop(0)
            else:
                self.program = kwargs.pop('program', None)
            if self.program is None:
                self.program = self.name
        else:
            char_seq = ''.join([string.lowercase, string.digits])
            self.program = kwargs.pop('program', None)
            if self.program is None:
                raise AttributeError('Must specify either "name" or "program" - both are unspecified.')
            self.name = os.path.basename(self.program)

        self.env = kwargs.pop('env', {})
        self.shell = kwargs.pop('shell', False)
        self._parent_dir = kwargs.pop('parent_dir', None)
        self.clean_on_exit = kwargs.pop('clean_on_exit', True)

        self.process = None
        self.created_parent_dir = False
        self._setup_done = False

        # Register the exit clean-up before making anything needing clean-up
        atexit.register(self.cleanup)


    def __enter__(self):
        '''
        Start a master and minion
        '''
        pass

    @property
    def start_pid(self):
        return self.process.pid if self.process else None

    @property
    def parent_dir(self):
        if self._parent_dir is None:
            self.created_parent_dir = True
            self._parent_dir = tempfile.mkdtemp(prefix='salt-testdaemon-XXXX')
            LOG.warning('TLH: mkdir: {0}'.format(self._parent_dir))
        else:
            self._parent_dir = os.path.abspath(os.path.normpath(self._parent_dir))
            if not os.path.exists(self._parent_dir):
                self.created_parent_dir = True
                os.makedirs(self._parent_dir)
                LOG.warning('TLH: mkdir: {0}'.format(self._parent_dir))
            elif not os.path.isdir(self._parent_dir):
                raise ValueError('Parent path "{0}" exists but is not a directory'.format(self._parent_dir))
        return self._parent_dir

    def setup(self, *args, **kwargs):
        LOG.warning('TLH: TestProgram.setup()')
        pass

    def cleanup(self, *args, **kwargs):
        '''
        Clean out the tmp files
        '''
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
            shell=False
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
        LOG.warning('TLH: TestProgram.run()')
        LOG.warning('TLH: {0}, type={1}'.format(self.name, type(self)))

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
                # detach from parent group (no more inherited signals!)
                os.setpgrp()

            popen_kwargs['preexec_fn'] = detach_from_parent_group

        elif sys.platform.lower().startswith('win') and timeout is not None:
            raise RuntimeError('Timeout is not supported under windows')

        argv = [self.program]
        argv.extend(args)
        LOG.warning('TLH: run(): {0}'.format(argv))
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
                        if exc.errno != 3:
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

    def __exit__(self, type, value, traceback):
        '''
        Kill the minion and master processes
        '''
        pass


_ = '''
class TestSaltProgramMeta(type):
    def __init__(cls, name, bases, attrs):
        if getattr(cls, 'script', None) is None:
            script = attrs.get('script')
            if script is None and 'Salt' in cls.__name__:
                script = 'salt-{0}'.format(cls.__name__.rsplit('Salt', 1)[-1].lower())
            if script is None:
                raise AttributeError('Class {0}: Unable to set "script" attribute: class name must include "Salt" or "script" must be explicitly set.'.format(cls.__name__))
            setattr(cls, 'script', script)
                
        super(TestSaltProgramMeta, cls).__init__(name, bases, attrs)
'''


class TestSaltProgram(TestProgram):

    script = ''

    def __init__(self, *args, **kwargs):
        LOG.warning('TLH: TestSaltProgram(*args={0}, **kwargs={1})'.format(args, kwargs))
        if 2 > len(args) and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        super(TestSaltProgram, self).__init__(*args, **kwargs)
        self.program = self.script_path

    @property
    def script_dir(self):
        return os.path.join(self.parent_dir, 'scripts')

    @property
    def script_path(self):
        return os.path.join(self.script_dir, self.script)

    def setup(self, *args, **kwargs):
        LOG.warning('TLH: TestSaltProgram.setup()')
        super(TestSaltProgram, self).setup(*args, **kwargs)
        self.install_script()

    def install_script(self):
        if not os.path.exists(self.script_dir):
            os.makedirs(self.script_dir)
            LOG.warning('TLH: install_script: {0}'.format(self._parent_dir))

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


class TestProgramSaltCall(TestSaltProgram):
    script = 'salt-call'


class TestDaemon(TestProgram):
    '''
    Run one of the standard daemons
    '''

    script = ''
    empty_config = ''
    pid_file = 'daemon.pid'
    config_file = 'config'

    config_types = (six.string_types,)


    def __init__(self, *args, **kwargs):
        self._config = kwargs.pop('config', copy.copy(self.empty_config))
        self.script = kwargs.pop('script', self.script)
        self.pid_file = kwargs.pop('pid_file', self.pid_file)
        self.config_file = kwargs.pop('config_file', self.config_file)
        if not args and 'program' not in kwargs:
            # This is effectively a place-holder - it gets set correctly after super()
            kwargs['program'] = self.script
        LOG.warning('TLH: TestDaemon(*args={0}, **kwargs={1})'.format(args, kwargs))
        super(TestDaemon, self).__init__(*args, **kwargs)
        self.program = self.script_path

    @property
    def root_dir(self):
        return os.path.join(self.parent_dir, self.name)

    @property
    def pid_path(self):
        return os.path.join(self.root_dir, 'var', 'run', self.pid_file)

    @property
    def daemon_pid(self):
        dpid = None
        with open(self.pid_path, 'r') as pf:
            dpid = pf.readline().strip()
        return dpid

    def wait_for_daemon_pid(self, timeout=0):
        endtime = time.time() + timeout
        while True:
            pid = self.daemon_pid
            if pid:
                return pid
            if endtime < time.time():
                raise TimeoutError('Timeout waiting for "{0}" pid in "{1}"'.format(self.name, self.pid_path))
            time.sleep(1.0)

    @property
    def config_dir(self):
        return os.path.join(self.root_dir, 'config')

    def setup(self, *args, **kwargs):
        LOG.warning('TLH: TestDaemon.setup()')
        super(TestDaemon, self).setup(*args, **kwargs)
        self.config_write()

    def cleanup(self, *args, **kwargs):
        super(TestDaemon, self).cleanup(*args, **kwargs)
        return
        if os.path.exists(self.root_dir):
            shutil.rmtree(self.root_dir)

    def config_write(self):
        LOG.warning('TLH: TestDaemon.setup()')
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            LOG.warning('TLH: mkdir: {0}'.format(self.config_dir))
        config_path = os.path.join(self.config_dir, self.config_file)
        with open(config_path, 'w') as cf:
            cf.write(self.config_stringify())
            cf.flush()

    def config_type(self, config):
        return isinstance(config, self.config_types)

    def config_cast(self, config):
        if not isinstance(config, six.string_types):
            config = str(config)
        return config

    def config_stringify(self):
        return self.config

    def config_merge(self, base, overrides):
        base = config_cast(base)
        overrides = config_cast(overrides)
        return ''.join([base, overrides])

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val):
        if val is None:
            val = ''
        self._config = self.config_cast(val)


_ = '''
class TestSaltDaemonMeta(type, TestSaltProgramMeta):
    def __init__(cls, name, bases, attrs):
        cls.config_attrs = {}
        for base in bases:
            cls.config_attrs.update(getattr(base, 'config_attrs', {}))
        cls.config_attrs.update(getattr(cls, 'config_attrs', {}))
'''


class TestSaltDaemon(TestDaemon, TestSaltProgram):

    config_types = (dict,)
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
    }
    script = ''
    empty_config = {}

    def __init__(self, *args, **kwargs):
        super(TestSaltDaemon, self).__init__(*args, **kwargs)
        path = self.env.get('PATH', os.getenv('PATH'))
        self.env['PATH'] = ':'.join([self.script_dir, path])

    def config_cast(self, config):
        if isinstance(config, six.string_types):
            config = yaml.safe_load(config)
        return config

    def config_merge(self, base, overrides):
        base = self.config_cast(copy.deepcopy(base))
        LOG.warning('TLH: config_merge(): base = {0}'.format(base))
        overrides = self.config_cast(overrides)
        LOG.warning('TLH: config_merge(): overrides = {0}'.format(overrides))
        # FIXME: this simple update will not work for deep dictionaries
        base.update(copy.deepcopy(overrides))
        LOG.warning('TLH: config_merge(): => {0}'.format(base))
        return base

    @property
    def config(self):
        attr_vals = dict([(k, getattr(self, v if v else k)) for k, v in self.config_attrs.items()])
        LOG.warning('TLH: config(): attr_vals = {0}'.format(attr_vals))
        LOG.warning('TLH: config(): _config = {0}'.format(self._config))
        merged = self.config_merge(self._config, attr_vals)
        LOG.warning('TLH: config() => {0}'.format(merged))
        return merged

    def config_stringify(self):
        return yaml.safe_dump(self.config, default_flow_style=False)


class TestDaemonSaltMaster(TestSaltDaemon):
    '''
    Manager for salt-master daemon.
    '''

    pid_file = 'salt-master.pid'
    script = 'salt-master'
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
    }
    config_file = 'master'


class TestDaemonSaltMinion(TestSaltDaemon):
    '''
    Manager for salt-minion daemon.
    '''

    pid_file = 'salt-minion.pid'
    script = 'salt-minion'
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
        'id': 'name',
    }
    config_file = 'minion'


class TestDaemonSaltApi(TestSaltDaemon):
    '''
    Manager for salt-api daemon.
    '''

    pid_file = 'salt-api.pid'
    script = 'salt-api'
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
    }


class TestDaemonSaltSyndic(TestSaltDaemon):
    '''
    Manager for salt-syndic daemon.
    '''

    pid_file = 'salt-syndic.pid'
    script = 'salt-syndic'
    config_attrs = {
        'root_dir': None,
        'config_dir': None,
    }
