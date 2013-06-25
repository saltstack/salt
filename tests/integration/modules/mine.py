'''
Test the salt mine system
'''

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


class MineTest(integration.ModuleCase):
    '''
    Test the mine system
    '''
    def test_get(self):
        '''
        test mine.get and mine.update
        '''
        self.assertTrue(self.run_function('mine.update', minion_tgt='minion'))
        self.assertTrue(
                self.run_function(
                    'mine.update',
                    minion_tgt='sub_minion'
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.get',
                    ['minion', 'test.ping']
                    )
                )

    def test_send(self):
        '''
        test mine.send
        '''
        self.assertFalse(
                self.run_function(
                    'mine.send',
                    ['foo.__spam_and_cheese']
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt='minion',
                    )
                )
        self.assertTrue(
                self.run_function(
                    'mine.send',
                    ['grains.items'],
                    minion_tgt='sub_minion',
                    )
                )
        ret = self.run_function(
                    'mine.get',
                    ['sub_minion', 'grains.items']
                    )
        self.assertEqual(ret['sub_minion']['id'], 'sub_minion')
        ret = self.run_function(
                    'mine.get',
                    ['minion', 'grains.items'],
                    minion_tgt='sub_minion'
                    )
        self.assertEqual(ret['minion']['id'], 'minion')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MineTest)
