# Import python libs
import integration


class PipModuleTest(integration.ModuleCase):
    '''
    Validate the pip module
    '''
    def setUp(self):
        super(PipModuleTest, self).setUp()
        ret = self.run_function(
            'cmd.which_bin', [['pip2', 'pip', 'pip-python']]
        )
        if not ret:
            self.skipTest("pip not installed")

    def test_freeze(self):
        '''
        pip.freeze
        '''
        ret = self.run_function('pip.freeze')
        self.assertIsInstance(ret, list)
        self.assertGreater(len(ret), 1)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PipModuleTest)
