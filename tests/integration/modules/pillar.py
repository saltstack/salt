# Import salt libs
import integration

class PillarModuleTest(integration.ModuleCase):
    '''
    Validate the pillar module
    '''
    def test_data(self):
        '''
        pillar.data
        '''
        self.assertEqual(self.run_function('pillar.data'), {'monty': 'python'})
