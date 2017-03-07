# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import sys
import textwrap
import tempfile

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    skip_if_binaries_missing
)
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


AVAILABLE_PYTHON_EXECUTABLE = salt.utils.which_bin([
    'python',
    'python2',
    'python2.6',
    'python2.7'

])


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CMDModuleTest(integration.ModuleCase):
    '''
    Validate the cmd module
    '''
    def test_run(self):
        '''
        cmd.run
        '''
        shell = os.environ.get('SHELL')
        if shell is None:
            # Failed to get the SHELL var, don't run
            self.skipTest('Unable to get the SHELL environment variable')

        self.assertTrue(self.run_function('cmd.run', ['echo $SHELL']))
        self.assertEqual(
            self.run_function('cmd.run',
                              ['echo $SHELL',
                               'shell={0}'.format(shell)],
                              python_shell=True).rstrip(), shell)
        self.assertEqual(self.run_function('cmd.run',
                          ['ls / | grep etc'],
                          python_shell=True), 'etc')
        self.assertEqual(self.run_function('cmd.run',
                         ['echo {{grains.id}} | awk "{print $1}"'],
                         template='jinja',
                         python_shell=True), 'minion')
        self.assertEqual(self.run_function('cmd.run',
                         ['grep f'],
                         stdin='one\ntwo\nthree\nfour\nfive\n'), 'four\nfive')
        self.assertEqual(self.run_function('cmd.run',
                         ['echo "a=b" | sed -e s/=/:/g'],
                         python_shell=True), 'a:b')

    @patch('pwd.getpwnam')
    @patch('subprocess.Popen')
    def test_os_environment_remains_intact(self,
                                           popen_mock,
                                           getpwnam_mock):
        '''
        Make sure the OS environment is not tainted after running a command
        that specifies runas.
        '''
        environment = os.environ.copy()

        popen_mock.return_value = Mock(
            communicate=lambda *args, **kwags: ['{}', None],
            pid=lambda: 1,
            retcode=0
        )

        from salt.modules import cmdmod

        cmdmod.__grains__ = {'os': 'Darwin', 'os_family': 'Solaris'}
        if sys.platform.startswith(('freebsd', 'openbsd')):
            shell = '/bin/sh'
        else:
            shell = '/bin/bash'

        try:
            cmdmod._run('ls',
                        cwd=tempfile.gettempdir(),
                        runas='foobar',
                        shell=shell)

            environment2 = os.environ.copy()

            self.assertEqual(environment, environment2)

            getpwnam_mock.assert_called_with('foobar')
        finally:
            delattr(cmdmod, '__grains__')

    def test_stdout(self):
        '''
        cmd.run_stdout
        '''
        self.assertEqual(self.run_function('cmd.run_stdout',
                                           ['echo "cheese"']).rstrip(),
                         'cheese')

    def test_stderr(self):
        '''
        cmd.run_stderr
        '''
        if sys.platform.startswith(('freebsd', 'openbsd')):
            shell = '/bin/sh'
        else:
            shell = '/bin/bash'

        self.assertEqual(self.run_function('cmd.run_stderr',
                                           ['echo "cheese" 1>&2',
                                            'shell={0}'.format(shell)], python_shell=True
                                           ).rstrip(),
                         'cheese')

    def test_run_all(self):
        '''
        cmd.run_all
        '''
        if sys.platform.startswith(('freebsd', 'openbsd')):
            shell = '/bin/sh'
        else:
            shell = '/bin/bash'

        ret = self.run_function('cmd.run_all', ['echo "cheese" 1>&2',
                                                'shell={0}'.format(shell)], python_shell=True)
        self.assertTrue('pid' in ret)
        self.assertTrue('retcode' in ret)
        self.assertTrue('stdout' in ret)
        self.assertTrue('stderr' in ret)
        self.assertTrue(isinstance(ret.get('pid'), int))
        self.assertTrue(isinstance(ret.get('retcode'), int))
        self.assertTrue(isinstance(ret.get('stdout'), six.string_types))
        self.assertTrue(isinstance(ret.get('stderr'), six.string_types))
        self.assertEqual(ret.get('stderr').rstrip(), 'cheese')

    def test_retcode(self):
        '''
        cmd.retcode
        '''
        self.assertEqual(self.run_function('cmd.retcode', ['exit 0'], python_shell=True), 0)
        self.assertEqual(self.run_function('cmd.retcode', ['exit 1'], python_shell=True), 1)

    def test_blacklist_glob(self):
        '''
        cmd_blacklist_glob
        '''
        self.assertEqual(self.run_function('cmd.run',
                ['bad_command --foo']).rstrip(),
                'ERROR: This shell command is not permitted: "bad_command --foo"')

    def test_script(self):
        '''
        cmd.script
        '''
        args = 'saltines crackers biscuits=yes'
        script = 'salt://script.py'
        ret = self.run_function('cmd.script', [script, args])
        self.assertEqual(ret['stdout'], args)

    def test_script_retcode(self):
        '''
        cmd.script_retcode
        '''
        script = 'salt://script.py'
        ret = self.run_function('cmd.script_retcode', [script])
        self.assertEqual(ret, 0)

    @destructiveTest
    def test_tty(self):
        '''
        cmd.tty
        '''
        for tty in ('tty0', 'pts3'):
            if os.path.exists(os.path.join('/dev', tty)):
                ret = self.run_function('cmd.tty', [tty, 'apply salt liberally'])
                self.assertTrue('Success' in ret)

    @skip_if_binaries_missing(['which'])
    def test_which(self):
        '''
        cmd.which
        '''
        self.assertEqual(self.run_function('cmd.which', ['cat']).rstrip(),
                         self.run_function('cmd.run', ['which cat']).rstrip())

    @skip_if_binaries_missing(['which'])
    def test_which_bin(self):
        '''
        cmd.which_bin
        '''
        cmds = ['pip2', 'pip', 'pip-python']
        ret = self.run_function('cmd.which_bin', [cmds])
        self.assertTrue(os.path.split(ret)[1] in cmds)

    def test_has_exec(self):
        '''
        cmd.has_exec
        '''
        self.assertTrue(self.run_function('cmd.has_exec',
                                          [AVAILABLE_PYTHON_EXECUTABLE]))
        self.assertFalse(self.run_function('cmd.has_exec',
                                           ['alllfsdfnwieulrrh9123857ygf']))

    def test_exec_code(self):
        '''
        cmd.exec_code
        '''
        code = textwrap.dedent('''\
               import sys
               sys.stdout.write('cheese')''')
        self.assertEqual(self.run_function('cmd.exec_code',
                                           [AVAILABLE_PYTHON_EXECUTABLE,
                                            code]).rstrip(),
                         'cheese')

    def test_quotes(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        expected_result = 'SELECT * FROM foo WHERE bar="baz"'
        result = self.run_function('cmd.run_stdout', [cmd]).strip()
        self.assertEqual(result, expected_result)

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_quotes_runas(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        expected_result = 'SELECT * FROM foo WHERE bar="baz"'

        try:
            runas = os.getlogin()
        except:  # pylint: disable=W0702
            # On some distros (notably Gentoo) os.getlogin() fails
            import pwd
            runas = pwd.getpwuid(os.getuid())[0]

        result = self.run_function('cmd.run_stdout', [cmd],
                                   runas=runas).strip()
        self.assertEqual(result, expected_result)

    def test_timeout(self):
        '''
        cmd.run trigger timeout
        '''
        out = self.run_function('cmd.run',
                                ['sleep 2 && echo hello'],
                                f_timeout=1,
                                python_shell=True)
        self.assertTrue('Timed out' in out)

    def test_timeout_success(self):
        '''
        cmd.run sufficient timeout to succeed
        '''
        out = self.run_function('cmd.run',
                                ['sleep 1 && echo hello'],
                                f_timeout=2,
                                python_shell=True)
        self.assertEqual(out, 'hello')

    def test_run_cwd_doesnt_exist_issue_7154(self):
        '''
        cmd.run should fail and raise
        salt.exceptions.CommandExecutionError if the cwd dir does not
        exist
        '''
        from salt.exceptions import CommandExecutionError
        import salt.modules.cmdmod as cmdmod
        cmd = 'echo OHAI'
        cwd = '/path/to/nowhere'
        try:
            cmdmod.run_all(cmd, cwd=cwd)
        except CommandExecutionError:
            pass
        else:
            raise RuntimeError
