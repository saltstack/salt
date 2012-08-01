# Import python libs
import os
import tempfile
import integration


class PipModuleTest(integration.ModuleCase):
    '''
    Validate the pip module
    '''

    # XXX: This module is almost a duplicate of tests/integration/virtualenv.py
    #      In fact pip.freeze is also tested in tests/integration/virtualenv.py
    #      Should this test case be removed?
    def setUp(self):
        super(PipModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['virtualenv'])
        if not ret:
            self.skipTest('virtualenv not installed')
        self.venv_test_dir = tempfile.mkdtemp()
        self.venv_dir = os.path.join(self.venv_test_dir, 'venv')
        self.run_function('virtualenv.create', [self.venv_dir])

        activate = os.path.join(self.venv_dir, 'bin', 'activate')
        if not os.path.isfile(activate):
            self.skipTest('Failed to create a proper virtualenv environment')

        ret = self.run_function('cmd.run', [
            "source {0}; which pip2 pip pip-python; deactivate".format(activate)
        ])
        if not ret:
            self.skipTest("unable to find proper pip binary")

        self.pip_bin = ret

    def test_freeze(self):
        '''
        pip.freeze
        '''
        ret = self.run_function('pip.freeze', bin_env=self.pip_bin)
        self.assertIsInstance(ret, list)
        self.assertGreater(len(ret), 1)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipModuleTest)
