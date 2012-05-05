# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


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

    def test_kwarg(self):
        '''
        Verify that the pub data is making it to the minion functions
        '''
        ret = self.run_function(
                'publish.full_data',
                [
                    'minion',
                    'test.kwarg',
                    'cheese=spam',
                ]
                )['minion']['ret']
        self.assertTrue('__pub_arg' in ret)
        self.assertTrue('__pub_id' in ret)
        self.assertTrue('__pub_fun' in ret)
        self.assertTrue('__pub_jid' in ret)
        self.assertTrue('__pub_tgt' in ret)
        self.assertTrue('__pub_tgt_type' in ret)
        self.assertTrue('__pub_ret' in ret)
        self.assertTrue('cheese' in ret)
        self.assertEqual(ret['cheese'], 'spam')
        self.assertEqual(ret['__pub_arg'], ['cheese=spam'])
        self.assertEqual(ret['__pub_id'], 'minion')
        self.assertEqual(ret['__pub_fun'], 'test.kwarg')

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

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(PublishModuleTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
