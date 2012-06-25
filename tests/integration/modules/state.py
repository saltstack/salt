# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class StateModuleTest(integration.ModuleCase):
    '''
    Validate the test module
    '''
    def test_show_highstate(self):
        '''
        state.show_highstate
        '''
        high = self.run_function('state.show_highstate')
        self.assertTrue(isinstance(high, dict))
        self.assertTrue('/testfile' in high)
        self.assertEqual(high['/testfile']['__env__'], 'base')

    def test_show_lowstate(self):
        '''
        state.show_lowstate
        '''
        low = self.run_function('state.show_lowstate')
        self.assertTrue(isinstance(low, list))
        self.assertTrue(isinstance(low[0], dict))

    def test_catch_recurse(self):
        '''
        state.show_sls used to catch a recursive ref
        '''
        err = self.run_function('state.sls', mods='recurse_fail')
        self.assertIn('recursive', err[0])

    def test_no_recurse(self):
        '''
        verify that a sls structure is NOT a recursive ref
        '''
        sls = self.run_function('state.show_sls', mods='recurse_ok')
        self.assertIn('snmpd', sls)

    def test_no_recurse_two(self):
        '''
        verify that a sls structure is NOT a recursive ref
        '''
        sls = self.run_function('state.show_sls', mods='recurse_ok_two')
        self.assertIn('/etc/nagios/nrpe.cfg', sls)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(StateModuleTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
