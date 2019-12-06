# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    ====================================
    Custom Salt TestCase Implementations
    ====================================

    Custom reusable :class:`TestCase<python2:unittest.TestCase>`
    implementations.
'''
# pylint: disable=repr-flag-used-in-string

# Import python libs
from __future__ import absolute_import, unicode_literals
import os
import re
import sys
import time
import stat
import errno
import signal
import textwrap
import logging
import tempfile
import subprocess
from datetime import datetime, timedelta

# Import salt testing libs
from tests.support.unit import TestCase
from tests.support.helpers import (
    RedirectStdStreams, requires_sshd_server, win32_kill_process_tree
)
from tests.support.runtests import RUNTIME_VARS
from tests.support.mixins import (
        AdaptedConfigurationTestCaseMixin,
        SaltClientTestCaseMixin,
        SaltMultimasterClientTestCaseMixin,
        )
from tests.support.paths import ScriptPathMixin, INTEGRATION_TEST_DIR, CODE_DIR, PYEXEC, SCRIPT_DIR

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import cStringIO, range  # pylint: disable=import-error

STATE_FUNCTION_RUNNING_RE = re.compile(
    r'''The function (?:"|')(?P<state_func>.*)(?:"|') is running as PID '''
    r'(?P<pid>[\d]+) and was started at (?P<date>.*) with jid (?P<jid>[\d]+)'
)
SCRIPT_TEMPLATES = {
    'salt': [
        'from salt.scripts import salt_main\n',
        'if __name__ == \'__main__\':'
        '    salt_main()'
    ],
    'salt-api': [
        'import salt.cli\n',
        'def main():',
        '    sapi = salt.cli.SaltAPI()',
        '    sapi.run()\n',
        'if __name__ == \'__main__\':',
        '    main()'
    ],
    'common': [
        'from salt.scripts import salt_{0}\n',
        'if __name__ == \'__main__\':',
        '    salt_{0}()'
    ]
}

log = logging.getLogger(__name__)


class ShellTestCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Execute a test for a shell command
    '''

    def get_script_path(self, script_name):
        '''
        Return the path to a testing runtime script
        '''
        if not os.path.isdir(RUNTIME_VARS.TMP_SCRIPT_DIR):
            os.makedirs(RUNTIME_VARS.TMP_SCRIPT_DIR)

        script_path = os.path.join(RUNTIME_VARS.TMP_SCRIPT_DIR, script_name)
        if not os.path.isfile(script_path):
            log.debug('Generating {0}'.format(script_path))

            # Late import
            import salt.utils.files

            with salt.utils.files.fopen(script_path, 'w') as sfh:
                script_template = SCRIPT_TEMPLATES.get(script_name, None)
                if script_template is None:
                    script_template = SCRIPT_TEMPLATES.get('common', None)
                if script_template is None:
                    raise RuntimeError(
                        '{0} does not know how to handle the {1} script'.format(
                            self.__class__.__name__,
                            script_name
                        )
                    )
                contents = (
                    '#!{0}\n'.format(sys.executable) +
                    '\n'.join(script_template).format(script_name.replace('salt-', ''))
                )
                sfh.write(contents)
                log.debug(
                    'Wrote the following contents to temp script %s:\n%s',
                    script_path, contents
                )
            st = os.stat(script_path)
            os.chmod(script_path, st.st_mode | stat.S_IEXEC)

        return script_path

    def run_salt(self, arg_str, with_retcode=False, catch_stderr=False, timeout=15):
        r'''
        Run the ``salt`` CLI tool with the provided arguments

        .. code-block:: python

            class MatchTest(ShellTestCase):
                def test_list(self):
                    """
                    test salt -L matcher
                    """
                    data = self.run_salt('-L minion test.ping')
                    data = '\n'.join(data)
                    self.assertIn('minion', data)
        '''
        arg_str = '-c {0} -t {1} {2}'.format(self.config_dir, timeout, arg_str)
        return self.run_script('salt', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, timeout=timeout)

    def run_ssh(self, arg_str, with_retcode=False, timeout=25,
                catch_stderr=False, wipe=False, raw=False):
        '''
        Execute salt-ssh
        '''
        arg_str = '{0} {1} -c {2} -i --priv {3} --roster-file {4} localhost {5} --out=json'.format(
            ' -W' if wipe else '',
            ' -r' if raw else '',
            self.config_dir,
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'key_test'),
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'roster'),
            arg_str
        )
        return self.run_script('salt-ssh', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr, raw=True, timeout=timeout)

    def run_run(self,
                arg_str,
                with_retcode=False,
                catch_stderr=False,
                asynchronous=False,
                timeout=60,
                config_dir=None,
                **kwargs):
        '''
        Execute salt-run
        '''
        asynchronous = kwargs.get('async', asynchronous)
        arg_str = '-c {0}{async_flag} -t {timeout} {1}'.format(
                config_dir or self.config_dir,
                arg_str,
                timeout=timeout,
                async_flag=' --async' if asynchronous else '')
        return self.run_script('salt-run',
                               arg_str,
                               with_retcode=with_retcode,
                               catch_stderr=catch_stderr,
                               timeout=timeout)

    def run_run_plus(self, fun, *arg, **kwargs):
        '''
        Execute the runner function and return the return data and output in a dict
        '''
        ret = {'fun': fun}

        # Late import
        import salt.config
        import salt.output
        import salt.runner
        from salt.ext.six.moves import cStringIO

        opts = salt.config.master_config(
            self.get_config_file_path('master')
        )

        opts_arg = list(arg)
        if kwargs:
            opts_arg.append({'__kwarg__': True})
            opts_arg[-1].update(kwargs)

        opts.update({'doc': False, 'fun': fun, 'arg': opts_arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret['return'] = runner.run()
            try:
                ret['jid'] = runner.jid
            except AttributeError:
                ret['jid'] = None

        # Compile output
        # TODO: Support outputters other than nested
        opts['color'] = False
        opts['output_file'] = cStringIO()
        try:
            salt.output.display_output(ret['return'], opts=opts)
            ret['out'] = opts['output_file'].getvalue()
        finally:
            opts['output_file'].close()

        return ret

    def run_key(self, arg_str, catch_stderr=False, with_retcode=False):
        '''
        Execute salt-key
        '''
        arg_str = '-c {0} {1}'.format(self.config_dir, arg_str)
        return self.run_script(
            'salt-key',
            arg_str,
            catch_stderr=catch_stderr,
            with_retcode=with_retcode
        )

    def run_cp(self, arg_str, with_retcode=False, catch_stderr=False):
        '''
        Execute salt-cp
        '''
        arg_str = '--config-dir {0} {1}'.format(self.config_dir, arg_str)
        return self.run_script('salt-cp', arg_str, with_retcode=with_retcode, catch_stderr=catch_stderr)

    def run_call(self, arg_str, with_retcode=False, catch_stderr=False, local=False, timeout=15):
        arg_str = '{0} --config-dir {1} {2}'.format('--local' if local else '',
                                                    self.config_dir, arg_str)

        return self.run_script('salt-call',
                               arg_str,
                               with_retcode=with_retcode,
                               catch_stderr=catch_stderr,
                               timeout=timeout)

    def run_cloud(self, arg_str, catch_stderr=False, timeout=None):
        '''
        Execute salt-cloud
        '''
        arg_str = '-c {0} {1}'.format(self.config_dir, arg_str)
        return self.run_script('salt-cloud', arg_str, catch_stderr, timeout)

    def run_script(self,
                   script,
                   arg_str,
                   catch_stderr=False,
                   with_retcode=False,
                   catch_timeout=False,
                   # FIXME A timeout of zero or disabling timeouts may not return results!
                   timeout=15,
                   raw=False,
                   popen_kwargs=None,
                   log_output=None):
        '''
        Execute a script with the given argument string

        The ``log_output`` argument is ternary, it can be True, False, or None.
        If the value is boolean, then it forces the results to either be logged
        or not logged. If it is None, then the return code of the subprocess
        determines whether or not to log results.
        '''

        import salt.utils.platform

        script_path = self.get_script_path(script)
        if not os.path.isfile(script_path):
            return False
        popen_kwargs = popen_kwargs or {}

        if salt.utils.platform.is_windows():
            cmd = 'python '
            if 'cwd' not in popen_kwargs:
                popen_kwargs['cwd'] = os.getcwd()
            if 'env' not in popen_kwargs:
                popen_kwargs['env'] = os.environ.copy()
                if sys.version_info[0] < 3:
                    popen_kwargs['env'][b'PYTHONPATH'] = CODE_DIR.encode()
                else:
                    popen_kwargs['env']['PYTHONPATH'] = CODE_DIR
        else:
            cmd = 'PYTHONPATH='
            python_path = os.environ.get('PYTHONPATH', None)
            if python_path is not None:
                cmd += '{0}:'.format(python_path)

            if sys.version_info[0] < 3:
                cmd += '{0} '.format(':'.join(sys.path[1:]))
            else:
                cmd += '{0} '.format(':'.join(sys.path[0:]))
            cmd += 'python{0}.{1} '.format(*sys.version_info)
        cmd += '{0} '.format(script_path)
        cmd += '{0} '.format(arg_str)

        tmp_file = tempfile.SpooledTemporaryFile()

        popen_kwargs = dict({
            'shell': True,
            'stdout': tmp_file,
            'universal_newlines': True,
        }, **popen_kwargs)

        if catch_stderr is True:
            popen_kwargs['stderr'] = subprocess.PIPE

        if not sys.platform.lower().startswith('win'):
            popen_kwargs['close_fds'] = True

            def detach_from_parent_group():
                # detach from parent group (no more inherited signals!)
                os.setpgrp()

            popen_kwargs['preexec_fn'] = detach_from_parent_group

        def format_return(retcode, stdout, stderr=None, timed_out=False):
            '''
            DRY helper to log script result if it failed, and then return the
            desired output based on whether or not stderr was desired, and
            wither or not a retcode was desired.
            '''
            log_func = log.debug
            if timed_out:
                log.error(
                    'run_script timed out after %d seconds (process killed)',
                    timeout
                )
                log_func = log.error

            if log_output is True \
                    or timed_out \
                    or (log_output is None and retcode != 0):
                log_func(
                    'run_script results for: %s %s\n'
                    'return code: %s\n'
                    'stdout:\n'
                    '%s\n\n'
                    'stderr:\n'
                    '%s',
                    script, arg_str, retcode, stdout, stderr
                )

            stdout = stdout or ''
            stderr = stderr or ''

            if not raw:
                stdout = stdout.splitlines()
                stderr = stderr.splitlines()

            ret = [stdout]
            if catch_stderr:
                ret.append(stderr)
            if with_retcode:
                ret.append(retcode)
            if catch_timeout:
                ret.append(timed_out)

            return ret[0] if len(ret) == 1 else tuple(ret)

        process = subprocess.Popen(cmd, **popen_kwargs)

        if timeout is not None:
            stop_at = datetime.now() + timedelta(seconds=timeout)
            term_sent = False
            while True:
                process.poll()
                time.sleep(0.1)
                if datetime.now() <= stop_at:
                    # We haven't reached the timeout yet
                    if process.returncode is not None:
                        break
                else:
                    # We've reached the timeout
                    if term_sent is False:
                        # Kill the process group since sending the term signal
                        # would only terminate the shell, not the command
                        # executed in the shell
                        if salt.utils.platform.is_windows():
                            _, alive = win32_kill_process_tree(process.pid)
                            if alive:
                                log.error("Child processes still alive: %s", alive)
                        else:
                            os.killpg(os.getpgid(process.pid), signal.SIGINT)
                        term_sent = True
                        continue

                    try:
                        # As a last resort, kill the process group
                        if salt.utils.platform.is_windows():
                            _, alive = win32_kill_process_tree(process.pid)
                            if alive:
                                log.error("Child processes still alive: %s", alive)
                        else:
                            os.killpg(os.getpgid(process.pid), signal.SIGINT)
                    except OSError as exc:
                        if exc.errno != errno.ESRCH:
                            # If errno is not "no such process", raise
                            raise

                    return format_return(
                        process.returncode,
                        *process.communicate(),
                        timed_out=True
                    )

        tmp_file.seek(0)

        if sys.version_info >= (3,):
            try:
                out = tmp_file.read().decode(__salt_system_encoding__)
            except (NameError, UnicodeDecodeError):
                # Let's cross our fingers and hope for the best
                out = tmp_file.read().decode('utf-8')
        else:
            out = tmp_file.read()

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
                err = process.stderr.read()
            else:
                _, err = process.communicate()
            # Force closing stderr/stdout to release file descriptors
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

            # pylint: disable=maybe-no-member
            try:
                return format_return(process.returncode, out, err or '')
            finally:
                try:
                    if os.path.exists(tmp_file.name):
                        if isinstance(tmp_file.name, six.string_types):
                            # tmp_file.name is an int when using SpooledTemporaryFiles
                            # int types cannot be used with os.remove() in Python 3
                            os.remove(tmp_file.name)
                        else:
                            # Clean up file handles
                            tmp_file.close()
                    process.terminate()
                except OSError as err:
                    # process already terminated
                    pass
            # pylint: enable=maybe-no-member

        # TODO Remove this?
        process.communicate()
        if process.stdout is not None:
            process.stdout.close()

        try:
            return format_return(process.returncode, out)
        finally:
            try:
                if os.path.exists(tmp_file.name):
                    if isinstance(tmp_file.name, six.string_types):
                        # tmp_file.name is an int when using SpooledTemporaryFiles
                        # int types cannot be used with os.remove() in Python 3
                        os.remove(tmp_file.name)
                    else:
                        # Clean up file handles
                        tmp_file.close()
                process.terminate()
            except OSError as err:
                # process already terminated
                pass


class MultiMasterTestShellCase(ShellTestCase):
    '''
    Execute a test for a shell command when running multi-master tests
    '''

    @property
    def config_dir(self):
        return RUNTIME_VARS.TMP_MM_CONF_DIR


class ShellCase(ShellTestCase, AdaptedConfigurationTestCaseMixin, ScriptPathMixin):
    '''
    Execute a test for a shell command
    '''

    _code_dir_ = CODE_DIR
    _script_dir_ = SCRIPT_DIR
    _python_executable_ = PYEXEC
    RUN_TIMEOUT = 500

    def chdir(self, dirname):
        try:
            os.chdir(dirname)
        except OSError:
            os.chdir(INTEGRATION_TEST_DIR)

    def run_salt(self, arg_str, with_retcode=False, catch_stderr=False,  # pylint: disable=W0221
            timeout=RUN_TIMEOUT, popen_kwargs=None):
        '''
        Execute salt
        '''
        arg_str = '-c {0} -t {1} {2}'.format(self.config_dir, timeout, arg_str)
        ret = self.run_script('salt',
                              arg_str,
                              with_retcode=with_retcode,
                              catch_stderr=catch_stderr,
                              timeout=timeout,
                              popen_kwargs=popen_kwargs)
        log.debug('Result of run_salt for command \'%s\': %s', arg_str, ret)
        return ret

    def run_spm(self, arg_str, with_retcode=False, catch_stderr=False, timeout=RUN_TIMEOUT):  # pylint: disable=W0221
        '''
        Execute spm
        '''
        ret = self.run_script('spm',
                              arg_str,
                              with_retcode=with_retcode,
                              catch_stderr=catch_stderr,
                              timeout=timeout)
        log.debug('Result of run_spm for command \'%s\': %s', arg_str, ret)
        return ret

    def run_ssh(self, arg_str, with_retcode=False, catch_stderr=False,  # pylint: disable=W0221
                timeout=RUN_TIMEOUT, wipe=True, raw=False):
        '''
        Execute salt-ssh
        '''
        arg_str = '{0} -ldebug{1} -c {2} -i --priv {3} --roster-file {4} --out=json localhost {5}'.format(
            ' -W' if wipe else '',
            ' -r' if raw else '',
            self.config_dir,
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'key_test'),
            os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'roster'),
            arg_str)
        ret = self.run_script('salt-ssh',
                              arg_str,
                              with_retcode=with_retcode,
                              catch_stderr=catch_stderr,
                              timeout=timeout,
                              raw=True)
        log.debug('Result of run_ssh for command \'%s\': %s', arg_str, ret)
        return ret

    def run_run(self, arg_str, with_retcode=False, catch_stderr=False,
            asynchronous=False, timeout=RUN_TIMEOUT, config_dir=None, **kwargs):
        '''
        Execute salt-run
        '''
        asynchronous = kwargs.get('async', asynchronous)
        arg_str = '-c {0}{async_flag} -t {timeout} {1}'.format(config_dir or self.config_dir,
                                                               arg_str,
                                                               timeout=timeout,
                                                               async_flag=' --async' if asynchronous else '')
        ret = self.run_script('salt-run',
                              arg_str,
                              with_retcode=with_retcode,
                              catch_stderr=catch_stderr,
                              timeout=timeout + 10)
        log.debug('Result of run_run for command \'%s\': %s', arg_str, ret)
        return ret

    def run_run_plus(self, fun, *arg, **kwargs):
        '''
        Execute the runner function and return the return data and output in a dict
        '''
        # Late import
        import salt.runner
        import salt.output
        ret = {'fun': fun}
        from_scratch = bool(kwargs.pop('__reload_config', False))
        # Have to create an empty dict and then update it, as the result from
        # self.get_config() is an ImmutableDict which cannot be updated.
        opts = {}
        opts.update(self.get_config('client_config', from_scratch=from_scratch))
        opts_arg = list(arg)
        if kwargs:
            opts_arg.append({'__kwarg__': True})
            opts_arg[-1].update(kwargs)
        opts.update({'doc': False, 'fun': fun, 'arg': opts_arg})
        with RedirectStdStreams():
            runner = salt.runner.Runner(opts)
            ret['return'] = runner.run()
            try:
                ret['jid'] = runner.jid
            except AttributeError:
                ret['jid'] = None

        # Compile output
        # TODO: Support outputters other than nested
        opts['color'] = False
        opts['output_file'] = cStringIO()
        try:
            salt.output.display_output(ret['return'], opts=opts)
            ret['out'] = opts['output_file'].getvalue().splitlines()
        finally:
            opts['output_file'].close()

        log.debug('Result of run_run_plus for fun \'%s\' with arg \'%s\': %s',
                  fun, opts_arg, ret)
        return ret

    def run_key(self, arg_str, catch_stderr=False, with_retcode=False,  # pylint: disable=W0221
            timeout=RUN_TIMEOUT):
        '''
        Execute salt-key
        '''
        arg_str = '-c {0} {1}'.format(self.config_dir, arg_str)
        ret = self.run_script('salt-key',
                              arg_str,
                              catch_stderr=catch_stderr,
                              with_retcode=with_retcode,
                              timeout=timeout)
        log.debug('Result of run_key for command \'%s\': %s', arg_str, ret)
        return ret

    def run_cp(self, arg_str, with_retcode=False, catch_stderr=False,  # pylint: disable=W0221
            timeout=RUN_TIMEOUT):
        '''
        Execute salt-cp
        '''
        # Note: not logging result of run_cp because it will log a bunch of
        # bytes which will not be very helpful.
        arg_str = '--config-dir {0} {1}'.format(self.config_dir, arg_str)
        return self.run_script('salt-cp',
                               arg_str,
                               with_retcode=with_retcode,
                               catch_stderr=catch_stderr,
                               timeout=timeout)

    def run_call(self, arg_str, with_retcode=False, catch_stderr=False,  # pylint: disable=W0221
            local=False, timeout=RUN_TIMEOUT):
        '''
        Execute salt-call.
        '''
        arg_str = '{0} --config-dir {1} {2}'.format('--local' if local else '',
                                                    self.config_dir, arg_str)
        ret = self.run_script('salt-call',
                              arg_str,
                              with_retcode=with_retcode,
                              catch_stderr=catch_stderr,
                              timeout=timeout)
        log.debug('Result of run_call for command \'%s\': %s', arg_str, ret)
        return ret

    def run_cloud(self, arg_str, catch_stderr=False, timeout=RUN_TIMEOUT):
        '''
        Execute salt-cloud
        '''
        arg_str = '-c {0} {1}'.format(self.config_dir, arg_str)
        ret = self.run_script('salt-cloud',
                              arg_str,
                              catch_stderr,
                              timeout=timeout)
        log.debug('Result of run_cloud for command \'%s\': %s', arg_str, ret)
        return ret


class SPMTestUserInterface(object):
    '''
    Test user interface to SPMClient
    '''
    def __init__(self):
        self._status = []
        self._confirm = []
        self._error = []

    def status(self, msg):
        self._status.append(msg)

    def confirm(self, action):
        self._confirm.append(action)

    def error(self, msg):
        self._error.append(msg)


class SPMCase(TestCase, AdaptedConfigurationTestCaseMixin):
    '''
    Class for handling spm commands
    '''

    def _spm_build_files(self, config):
        self.formula_dir = os.path.join(' '.join(config['file_roots']['base']), 'formulas')
        self.formula_sls_dir = os.path.join(self.formula_dir, 'apache')
        self.formula_sls = os.path.join(self.formula_sls_dir, 'apache.sls')
        self.formula_file = os.path.join(self.formula_dir, 'FORMULA')

        dirs = [self.formula_dir, self.formula_sls_dir]
        for f_dir in dirs:
            os.makedirs(f_dir)

        # Late import
        import salt.utils.files

        with salt.utils.files.fopen(self.formula_sls, 'w') as fp:
            fp.write(textwrap.dedent('''\
                     install-apache:
                       pkg.installed:
                         - name: apache2
                     '''))

        with salt.utils.files.fopen(self.formula_file, 'w') as fp:
            fp.write(textwrap.dedent('''\
                     name: apache
                     os: RedHat, Debian, Ubuntu, Suse, FreeBSD
                     os_family: RedHat, Debian, Suse, FreeBSD
                     version: 201506
                     release: 2
                     summary: Formula for installing Apache
                     description: Formula for installing Apache
                     '''))

    def _spm_config(self, assume_yes=True):
        self._tmp_spm = tempfile.mkdtemp()
        config = self.get_temp_config('minion', **{
            'spm_logfile': os.path.join(self._tmp_spm, 'log'),
            'spm_repos_config': os.path.join(self._tmp_spm, 'etc', 'spm.repos'),
            'spm_cache_dir': os.path.join(self._tmp_spm, 'cache'),
            'spm_build_dir': os.path.join(self._tmp_spm, 'build'),
            'spm_build_exclude': ['apache/.git'],
            'spm_db_provider': 'sqlite3',
            'spm_files_provider': 'local',
            'spm_db': os.path.join(self._tmp_spm, 'packages.db'),
            'extension_modules': os.path.join(self._tmp_spm, 'modules'),
            'file_roots': {'base': [self._tmp_spm, ]},
            'formula_path': os.path.join(self._tmp_spm, 'salt'),
            'pillar_path': os.path.join(self._tmp_spm, 'pillar'),
            'reactor_path': os.path.join(self._tmp_spm, 'reactor'),
            'assume_yes': True if assume_yes else False,
            'force': False,
            'verbose': False,
            'cache': 'localfs',
            'cachedir': os.path.join(self._tmp_spm, 'cache'),
            'spm_repo_dups': 'ignore',
            'spm_share_dir': os.path.join(self._tmp_spm, 'share'),
        })

        import salt.utils.files
        import salt.utils.yaml

        if not os.path.isdir(config['formula_path']):
            os.makedirs(config['formula_path'])

        with salt.utils.files.fopen(os.path.join(self._tmp_spm, 'spm'), 'w') as fp:
            salt.utils.yaml.safe_dump(config, fp)

        return config

    def _spm_create_update_repo(self, config):

        build_spm = self.run_spm('build', self.config, self.formula_dir)

        c_repo = self.run_spm('create_repo', self.config,
                              self.config['spm_build_dir'])

        repo_conf_dir = self.config['spm_repos_config'] + '.d'
        os.makedirs(repo_conf_dir)

        # Late import
        import salt.utils.files

        with salt.utils.files.fopen(os.path.join(repo_conf_dir, 'spm.repo'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                     local_repo:
                       url: file://{0}
                     '''.format(self.config['spm_build_dir'])))

        u_repo = self.run_spm('update_repo', self.config)

    def _spm_client(self, config):
        import salt.spm
        self.ui = SPMTestUserInterface()
        client = salt.spm.SPMClient(self.ui, config)
        return client

    def run_spm(self, cmd, config, arg=None):
        client = self._spm_client(config)
        spm_cmd = client.run([cmd, arg])
        client._close()
        return self.ui._status


class ModuleCase(TestCase, SaltClientTestCaseMixin):
    '''
    Execute a module function
    '''

    def wait_for_all_jobs(self, minions=('minion', 'sub_minion',), sleep=.3):
        '''
        Wait for all jobs currently running on the list of minions to finish
        '''
        for minion in minions:
            while True:
                ret = self.run_function('saltutil.running', minion_tgt=minion, timeout=300)
                if ret:
                    log.debug('Waiting for minion\'s jobs: %s', minion)
                    time.sleep(sleep)
                else:
                    break

    def minion_run(self, _function, *args, **kw):
        '''
        Run a single salt function on the 'minion' target and condition
        the return down to match the behavior of the raw function call
        '''
        return self.run_function(_function, args, **kw)

    def run_function(self, function, arg=(), minion_tgt='minion', timeout=300, master_tgt=None, **kwargs):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        known_to_return_none = (
            'data.get',
            'file.chown',
            'file.chgrp',
            'pkg.refresh_db',
            'ssh.recv_known_host_entries',
            'time.sleep'
        )
        if minion_tgt == 'sub_minion':
            known_to_return_none += ('mine.update',)
        if 'f_arg' in kwargs:
            kwargs['arg'] = kwargs.pop('f_arg')
        if 'f_timeout' in kwargs:
            kwargs['timeout'] = kwargs.pop('f_timeout')
        client = self.client if master_tgt is None else self.clients[master_tgt]
        orig = client.cmd(minion_tgt,
                          function,
                          arg,
                          timeout=timeout,
                          kwarg=kwargs)

        if minion_tgt not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion \'{0}\'. Command output: {1}'.format(
                    minion_tgt, orig
                )
            )
        elif orig[minion_tgt] is None and function not in known_to_return_none:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get \'{0}\' from '
                'the minion \'{1}\'. Command output: {2}'.format(
                    function, minion_tgt, orig
                )
            )

        # Try to match stalled state functions
        orig[minion_tgt] = self._check_state_return(orig[minion_tgt])

        return orig[minion_tgt]

    def run_function_all_masters(self, function, arg=(), minion_tgt='minion', timeout=300, **kwargs):
        '''
        Run a single salt function from all the masters in multimaster environment
        and condition the return down to match the behavior of the raw function call
        '''
        ret = []
        for master in range(len(self.clients)):
            ret.append(self.run_function(function, arg, minion_tgt, timeout, master_tgt=master, **kwargs))
        return ret

    def run_state(self, function, **kwargs):
        '''
        Run the state.single command and return the state return structure
        '''
        ret = self.run_function('state.single', [function], **kwargs)
        return self._check_state_return(ret)

    def _check_state_return(self, ret):
        if isinstance(ret, dict):
            # This is the supposed return format for state calls
            return ret

        if isinstance(ret, list):
            jids = []
            # These are usually errors
            for item in ret[:]:
                if not isinstance(item, six.string_types):
                    # We don't know how to handle this
                    continue
                match = STATE_FUNCTION_RUNNING_RE.match(item)
                if not match:
                    # We don't know how to handle this
                    continue
                jid = match.group('jid')
                if jid in jids:
                    continue

                jids.append(jid)

                job_data = self.run_function('saltutil.find_job', [jid])
                job_kill = self.run_function('saltutil.kill_job', [jid])
                msg = (
                    'A running state.single was found causing a state lock. '
                    'Job details: \'{0}\'  Killing Job Returned: \'{1}\''.format(
                        job_data, job_kill
                    )
                )
                ret.append('[TEST SUITE ENFORCED]{0}'
                           '[/TEST SUITE ENFORCED]'.format(msg))
        return ret


class MultimasterModuleCase(ModuleCase, SaltMultimasterClientTestCaseMixin):
    '''
    Execute a module function
    '''

    def run_function(self, function, arg=(), minion_tgt='minion', timeout=300, master_tgt=0, **kwargs):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        known_to_return_none = (
            'data.get',
            'file.chown',
            'file.chgrp',
            'pkg.refresh_db',
            'ssh.recv_known_host_entries',
            'time.sleep'
        )
        if minion_tgt == 'sub_minion':
            known_to_return_none += ('mine.update',)
        if 'f_arg' in kwargs:
            kwargs['arg'] = kwargs.pop('f_arg')
        if 'f_timeout' in kwargs:
            kwargs['timeout'] = kwargs.pop('f_timeout')
        orig = self.clients[master_tgt].cmd(minion_tgt,
                                            function,
                                            arg,
                                            timeout=timeout,
                                            kwarg=kwargs)

        if minion_tgt not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion \'{0}\'. Command output: {1}'.format(
                    minion_tgt, orig
                )
            )
        elif orig[minion_tgt] is None and function not in known_to_return_none:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get \'{0}\' from '
                'the minion \'{1}\'. Command output: {2}'.format(
                    function, minion_tgt, orig
                )
            )

        # Try to match stalled state functions
        orig[minion_tgt] = self._check_state_return(orig[minion_tgt])

        return orig[minion_tgt]

    def run_function_all_masters(self, function, arg=(), minion_tgt='minion', timeout=300, **kwargs):
        '''
        Run a single salt function from all the masters in multimaster environment
        and condition the return down to match the behavior of the raw function call
        '''
        ret = []
        for master in range(len(self.clients)):
            ret.append(self.run_function(function, arg, minion_tgt, timeout, master_tgt=master, **kwargs))
        return ret


class SyndicCase(TestCase, SaltClientTestCaseMixin):
    '''
    Execute a syndic based execution test
    '''
    _salt_client_config_file_name_ = 'syndic_master'

    def run_function(self, function, arg=(), timeout=90):
        '''
        Run a single salt function and condition the return down to match the
        behavior of the raw function call
        '''
        orig = self.client.cmd('minion', function, arg, timeout=timeout)
        if 'minion' not in orig:
            self.skipTest(
                'WARNING(SHOULD NOT HAPPEN #1935): Failed to get a reply '
                'from the minion. Command output: {0}'.format(orig)
            )
        return orig['minion']


@requires_sshd_server
class SSHCase(ShellCase):
    '''
    Execute a command via salt-ssh
    '''
    def _arg_str(self, function, arg):
        return '{0} {1}'.format(function, ' '.join(arg))

    def run_function(self, function, arg=(), timeout=180, wipe=True, raw=False, **kwargs):
        '''
        We use a 180s timeout here, which some slower systems do end up needing
        '''
        ret = self.run_ssh(self._arg_str(function, arg), timeout=timeout,
                           wipe=wipe, raw=raw)
        log.debug('SSHCase run_function executed %s with arg %s', function, arg)
        log.debug('SSHCase JSON return: %s', ret)

        # Late import
        import salt.utils.json

        try:
            return salt.utils.json.loads(ret)['localhost']
        except Exception:
            return ret


class ClientCase(AdaptedConfigurationTestCaseMixin, TestCase):
    '''
    A base class containing relevant options for starting the various Salt
    Python API entrypoints
    '''
    def get_opts(self):
        # Late import
        import salt.config

        return salt.config.client_config(self.get_config_file_path('master'))

    def mkdir_p(self, path):
        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


# ----- Backwards Compatible Imports -------------------------------------------------------------------------------->
from tests.support.mixins import ShellCaseCommonTestsMixin  # pylint: disable=unused-import
# <---- Backwards Compatible Imports ---------------------------------------------------------------------------------
