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
        test mine.get and mine.update
        '''
        self.assertTrue(self.run_function('mine.update'))
        self.assertTrue(self.run_function('mine.get', ['minion', 'test.ping']))

    def test_send(self):
        '''
        test mine.send
        '''
        self.assertFalse(self.run_function('mine.send', ['foo.__spam_and_cheese']))
        self.assertTrue(self.run_function('mine.send', ['test.retcode']))
        self.assertTrue(self.run_function('mine.get', ['minion', 'test.retcode']))
