import os
import integration


class CMDModuleTest(integration.ModuleCase):
    '''
    Validate the cmd module
    '''
    def test_run(self):
        '''
        cmd.run
        '''
        shell = os.environ['SHELL']
        self.assertTrue(self.run_function('cmd.run', ['echo $SHELL']))
        self.assertEqual(
                self.run_function('cmd.run',
                    ['echo $SHELL', 'shell={0}'.format(shell)]).rstrip(),
                shell)

    def test_stdout(self):
        '''
        cmd.run_stdout
        '''
        self.assertEqual(
                self.run_function('cmd.run_stdout',
                    ['echo "cheese"']).rstrip(),
                'cheese')

    def test_stderr(self):
        '''
        cmd.run_stderr
        '''
        self.assertEqual(
                self.run_function('cmd.run_stderr',
                    ['echo "cheese" 1>&2']).rstrip(),
                'cheese')

    def test_run_all(self):
        '''
        cmd.run_all
        '''
        from salt._compat import string_types
        ret = self.run_function('cmd.run_all', ['echo "cheese" 1>&2'])
        self.assertTrue('pid' in ret)
        self.assertTrue('retcode' in ret)
        self.assertTrue('stdout' in ret)
        self.assertTrue('stderr' in ret)
        self.assertTrue(isinstance(ret.get('pid'), int))
        self.assertTrue(isinstance(ret.get('retcode'), int))
        self.assertTrue(isinstance(ret.get('stdout'), string_types))
        self.assertTrue(isinstance(ret.get('stderr'), string_types))
        self.assertEqual(ret.get('stderr').rstrip(), 'cheese')

    def test_retcode(self):
        '''
        cmd.retcode
        '''
        self.assertEqual(self.run_function('cmd.retcode', ['true']), 0)
        self.assertEqual(self.run_function('cmd.retcode', ['false']), 1)

    def test_which(self):
        '''
        cmd.which
        '''
        self.assertEqual(
                self.run_function('cmd.which', ['cat']).rstrip(),
                self.run_function('cmd.run', ['which cat']).rstrip())

    def test_has_exec(self):
        '''
        cmd.has_exec
        '''
        self.assertTrue(self.run_function('cmd.has_exec', ['python']))
        self.assertFalse(self.run_function(
            'cmd.has_exec',
            ['alllfsdfnwieulrrh9123857ygf']
            ))

    def test_exec_code(self):
        '''
        cmd.exec_code
        '''
        code = '''
import sys
sys.stdout.write('cheese')
        '''
        self.assertEqual(
                self.run_function('cmd.exec_code', ['python', code]).rstrip(),
                'cheese'
                )

    def test_quotes(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        expected_result = 'SELECT * FROM foo WHERE bar="baz"'
        result = self.run_function('cmd.run_stdout', [cmd]).strip()
        self.assertEqual(result, expected_result)

    def test_quotes_runas(self):
        '''
        cmd.run with quoted command
        '''
        cmd = '''echo 'SELECT * FROM foo WHERE bar="baz"' '''
        expected_result = 'SELECT * FROM foo WHERE bar="baz"'

        try:
            runas=os.getlogin()
        except:
            # On some distros (notably Gentoo) os.getlogin() fails
            import pwd
            runas=pwd.getpwuid(os.getuid())[0]

        result = self.run_function('cmd.run_stdout', [cmd],
                                   runas=runas).strip()
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CMDModuleTest)
