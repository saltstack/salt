# Import salt libs
import integration

class KeyTest(integration.CliCase):
    '''
    Test salt-key script
    '''
    def test_list(self):
        '''
        test salt-key -L
        '''
        data = self.run_key('-L')
        expect = [
                '\x1b[1;31mUnaccepted Keys:\x1b[0m',
                '\x1b[1;32mAccepted Keys:\x1b[0m',
                '\x1b[0;32mminion\x1b[0m',
                '\x1b[1;34mRejected:\x1b[0m', '']
        self.assertEqual(data, expect)
