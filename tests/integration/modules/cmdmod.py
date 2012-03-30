# Import python libs
import os

# Import salt libs
import integration

class CMDModuleTest(integration.ModuleCase):
    '''
    Validate the cmd module
    '''
    def test_run(self):
        '''
        cmd.run
        '''
        self.assertTrue(self.run_function('cmd.run', ['echo $SHELL']))
        self.assertEqual(
                self.run_function('cmd.run',
                    ['echo $SHELL', 'shell=/bin/bash']),
                '/bin/bash')

    def test_stdout(self):
        '''
        cmd.run_stdout
        '''
        self.assertEqual(
                self.run_function('cmd.run_stdout',
                    ['echo "cheese"']),
                'cheese')

    def test_stderr(self):
        '''
        cmd.run_stderr
        '''
        self.assertEqual(
                self.run_function('cmd.run_stderr',
                    ['echo "cheese" 1>&2']),
                'cheese')

    def test_run_all(self):
        '''
        cmd.run_all
        '''
        ret = self.run_function('cmd.run_all', ['echo "cheese" 1>&2'])
        self.assertTrue('pid' in ret)
        self.assertTrue('retcode' in ret)
        self.assertTrue('stdout' in ret)
        self.assertTrue('stderr' in ret)
        self.assertTrue(isinstance(ret.get('pid'), int))
        self.assertTrue(isinstance(ret.get('retcode'), int))
        self.assertTrue(isinstance(ret.get('stdout'), basestring))
        self.assertTrue(isinstance(ret.get('stderr'), basestring))
        self.assertEqual(ret.get('stderr'), 'cheese')

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
                self.run_function('cmd.which', ['echo']),
                self.run_function('cmd.run', ['which echo']))

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
                self.run_function('cmd.exec_code', ['python', code]),
                'cheese'
                )
