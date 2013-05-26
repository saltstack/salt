'''
Test the salt mine system
'''
import integration

class MineTest(integration.ModuleCase):
    '''
    Test the mine system
    '''
    def test_get(self):
        '''
        test mine.get
        '''
        self.assertTrue(self.run_function('mine.update'))
        self.assertTrue(self.run_function('mine.get', ['minion', 'test.ping']))
