# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import random
import sys
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    skip_if_binaries_missing,
    skip_if_not_root,
    this_user,
)
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

# Import salt libs
import salt.utils.path
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six

AVAILABLE_PYTHON_EXECUTABLE = salt.utils.path.which_bin([
    'python',
    'python2',
    'python2.6',
    'python2.7'

])


class CMDModuleTest(ModuleCase):
    '''
    Validate the cmd module
    '''
    def setUp(self):
        self.runas_usr = 'nobody'
        if salt.utils.platform.is_darwin():
            self.runas_usr = 'macsalttest'

    def tearDown(self):
        if self._testMethodName == 'test_runas':
            if salt.utils.platform.is_darwin():
                if self.runas_usr in self.run_function('user.info', [self.runas_usr]).values():
                    self.run_function('user.delete', [self.runas_usr], remove=True)

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

    def test_stdout(self):
        '''
        cmd.run_stdout
        '''
        self.assertEqual(self.run_function('cmd.run_stdout',
                                           ['echo "cheese"']).rstrip(),
                         'cheese' if not salt.utils.platform.is_windows() else '"cheese"')

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
                         'cheese' if not salt.utils.platform.is_windows() else '"cheese"')

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
        self.assertEqual(ret.get('stderr').rstrip(), 'cheese' if not salt.utils.platform.is_windows() else '"cheese"')

    def test_retcode(self):
        '''
        cmd.retcode
        '''
        self.assertEqual(self.run_function('cmd.retcode', ['exit 0'], python_shell=True), 0)
        self.assertEqual(self.run_function('cmd.retcode', ['exit 1'], python_shell=True), 1)

    def test_run_all_with_success_retcodes(self):
        '''
        cmd.run with success_retcodes
        '''
        ret = self.run_function('cmd.run_all',
                                ['exit 42'],
                                success_retcodes=[42],
                                python_shell=True)

        self.assertTrue('retcode' in ret)
        self.assertEqual(ret.get('retcode'), 0)

    def test_retcode_with_success_retcodes(self):
        '''
        cmd.run with success_retcodes
        '''
        ret = self.run_function('cmd.retcode',
                                ['exit 42'],
                                success_retcodes=[42],
                                python_shell=True)

        self.assertEqual(ret, 0)

    def test_run_all_with_success_stderr(self):
        '''
        cmd.run with success_retcodes
        '''
        random_file = "{0}{1}{2}".format(RUNTIME_VARS.TMP_ROOT_DIR,
                                         os.path.sep,
                                         random.random())

        if salt.utils.platform.is_windows():
            func = 'type'
            expected_stderr = 'The system cannot find the file specified.'
        else:
            func = 'cat'
            expected_stderr = 'cat: {0}: No such file or directory'.format(random_file)
        ret = self.run_function('cmd.run_all',
                                ['{0} {1}'.format(func, random_file)],
                                success_stderr=[expected_stderr],
                                python_shell=True)

        self.assertTrue('retcode' in ret)
        self.assertEqual(ret.get('retcode'), 0)

    def test_blacklist_glob(self):
        '''
        cmd_blacklist_glob
        '''
        self.assertEqual(self.run_function('cmd.run',
                ['bad_command --foo']).rstrip(),
                'ERROR: The shell command "bad_command --foo" is not permitted')

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

    def test_script_cwd(self):
        '''
        cmd.script with cwd
        '''
        tmp_cwd = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        args = 'saltines crackers biscuits=yes'
        script = 'salt://script.py'
        ret = self.run_function('cmd.script', [script, args], cwd=tmp_cwd)
        self.assertEqual(ret['stdout'], args)

    def test_script_cwd_with_space(self):
        '''
        cmd.script with cwd
        '''
        tmp_cwd = "{0}{1}test 2".format(tempfile.mkdtemp(dir=RUNTIME_VARS.TMP), os.path.sep)
        os.mkdir(tmp_cwd)

        args = 'saltines crackers biscuits=yes'
        script = 'salt://script.py'
        ret = self.run_function('cmd.script', [script, args], cwd=tmp_cwd)
        self.assertEqual(ret['stdout'], args)

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
        cmds = ['pip3', 'pip2', 'pip', 'pip-python']
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

    def test_exec_code_with_single_arg(self):
        '''
        cmd.exec_code
        '''
        code = textwrap.dedent('''\
               import sys
               sys.stdout.write(sys.argv[1])''')
        arg = 'cheese'
        self.assertEqual(self.run_function('cmd.exec_code',
                                           [AVAILABLE_PYTHON_EXECUTABLE,
                                            code],
                                           args=arg).rstrip(),
                         arg)

    def test_exec_code_with_multiple_args(self):
        '''
        cmd.exec_code
        '''
        code = textwrap.dedent('''\
               import sys
               sys.stdout.write(sys.argv[1])''')
        arg = 'cheese'
        self.assertEqual(self.run_function('cmd.exec_code',
                                           [AVAILABLE_PYTHON_EXECUTABLE,
                                            code],
                                           args=[arg, 'test']).rstrip(),
                         arg)

    def test_quotes(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        expected_result = 'SELECT * FROM foo WHERE bar="baz"'
        if salt.utils.platform.is_windows():
            expected_result = '\'SELECT * FROM foo WHERE bar="baz"\''
        result = self.run_function('cmd.run_stdout', [cmd]).strip()
        self.assertEqual(result, expected_result)

    @skip_if_not_root
    @skipIf(salt.utils.platform.is_windows, 'skip windows, requires password')
    def test_quotes_runas(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        if salt.utils.platform.is_darwin():
            cmd = '''echo 'SELECT * FROM foo WHERE bar=\\"baz\\"' '''

        expected_result = 'SELECT * FROM foo WHERE bar="baz"'

        runas = this_user()

        result = self.run_function('cmd.run_stdout', [cmd],
                                   runas=runas).strip()
        self.assertEqual(result, expected_result)

    @skipIf(salt.utils.platform.is_windows(), 'minion is windows')
    @skip_if_not_root
    @destructiveTest
    def test_runas(self):
        '''
        Ensure that the env is the runas user's
        '''
        if salt.utils.platform.is_darwin():
            if self.runas_usr not in self.run_function('user.info', [self.runas_usr]).values():
                self.run_function('user.add', [self.runas_usr])

        out = self.run_function('cmd.run', ['env'], runas=self.runas_usr).splitlines()
        self.assertIn('USER={0}'.format(self.runas_usr), out)

    @skipIf(not salt.utils.path.which_bin('sleep'), 'sleep cmd not installed')
    def test_timeout(self):
        '''
        cmd.run trigger timeout
        '''
        out = self.run_function('cmd.run',
                                ['sleep 2 && echo hello'],
                                f_timeout=1,
                                python_shell=True)
        self.assertTrue('Timed out' in out)

    @skipIf(not salt.utils.path.which_bin('sleep'), 'sleep cmd not installed')
    def test_timeout_success(self):
        '''
        cmd.run sufficient timeout to succeed
        '''
        out = self.run_function('cmd.run',
                                ['sleep 1 && echo hello'],
                                f_timeout=2,
                                python_shell=True)
        self.assertEqual(out, 'hello')

    def test_hide_output(self):
        '''
        Test the hide_output argument
        '''
        ls_command = ['ls', '/'] \
            if not salt.utils.platform.is_windows() \
            else ['dir', 'c:\\']

        error_command = ['thiscommanddoesnotexist']

        # cmd.run
        out = self.run_function(
            'cmd.run',
            ls_command,
            hide_output=True)
        self.assertEqual(out, '')

        # cmd.shell
        out = self.run_function(
            'cmd.shell',
            ls_command,
            hide_output=True)
        self.assertEqual(out, '')

        # cmd.run_stdout
        out = self.run_function(
            'cmd.run_stdout',
            ls_command,
            hide_output=True)
        self.assertEqual(out, '')

        # cmd.run_stderr
        out = self.run_function(
            'cmd.shell',
            error_command,
            hide_output=True)
        self.assertEqual(out, '')

        # cmd.run_all (command should have produced stdout)
        out = self.run_function(
            'cmd.run_all',
            ls_command,
            hide_output=True)
        self.assertEqual(out['stdout'], '')
        self.assertEqual(out['stderr'], '')

        # cmd.run_all (command should have produced stderr)
        out = self.run_function(
            'cmd.run_all',
            error_command,
            hide_output=True)
        self.assertEqual(out['stdout'], '')
        self.assertEqual(out['stderr'], '')

    def test_cmd_run_whoami(self):
        '''
        test return of whoami
        '''
        cmd = self.run_function('cmd.run', ['whoami'])
        if salt.utils.platform.is_windows():
            self.assertIn('administrator', cmd)
        else:
            self.assertEqual('root', cmd)
