# Import python libs
import sys

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration

# Import Salt Testing libs
from salttesting import TestLoader, TextTestRunner


class StdTest(integration.ModuleCase):
    '''
    Test standard client calls
    '''
    def test_cli(self):
        '''
        Test cli function
        '''
        cmd_iter = self.client.cmd_cli(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_iter(self):
        '''
        test cmd_iter
        '''
        cmd_iter = self.client.cmd_iter(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_iter_no_block(self):
        '''
        test cmd_iter_no_block
        '''
        cmd_iter = self.client.cmd_iter_no_block(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        for ret in cmd_iter:
            if ret is None:
                continue
            data = ret['minion']['ret']
            self.assertIn('foo', data)
            self.assertIn('baz', data)
            self.assertIn('qux', data)
            self.assertEqual(data['foo'], 'bar')
            self.assertEqual(data['baz'], 'quo')
            self.assertEqual(data['qux'], 'quux')

    def test_full_returns(self):
        '''
        test cmd_iter
        '''
        ret = self.client.cmd_full_return(
                'minion',
                'test.kwarg',
                ['foo=bar', 'baz=quo'],
                kwarg={'qux': 'quux'}
                )
        data = ret['minion']
        self.assertIn('foo', data['ret'])
        self.assertIn('baz', data['ret'])
        self.assertIn('qux', data['ret'])
        self.assertEqual(data['ret']['foo'], 'bar')
        self.assertEqual(data['ret']['baz'], 'quo')
        self.assertEqual(data['ret']['qux'], 'quux')

if __name__ == "__main__":
    from integration import run_tests
    run_tests(StdTest)
