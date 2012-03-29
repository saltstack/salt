# Import salt libs
import integration

class PublishModuleTest(integration.ModuleCase):
    '''
    Validate the publish module
    '''
    def test_publish(self):
        '''
        publish.publish
        '''
        ret = self.run_function('publish.publish', ['minion', 'test.ping'])
        self.assertTrue(ret['minion'])

    def test_full_data(self):
        '''
        publish.full_data
        '''
        ret = self.run_function(
                'publish.full_data',
                [
                    'minion',
                    'test.fib',
                    ['40']
                ]
                )
        self.assertEqual(ret['minion']['ret'][0][-1], 34)
        
    def test_reject_minion(self):
        '''
        Test bad authentication
        '''
        ret = self.run_function(
                'publish.publish',
                [
                    'minion',
                    'cmd.run',
                    ['echo foo']
                ]
                )
        self.assertEqual(ret, {})
