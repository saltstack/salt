# Import python libs
import os

# Import salt libs
import integration

class CPModuleTest(integration.ModuleCase):
    '''
    Validate the test module
    '''
    def test_get_file(self):
        '''
        cp.get_file
        '''
        tgt = os.path.join(integration.TMP, 'scene33')
        self.run_function(
                'cp.get_file',
                [
                    'salt://grail/scene33',
                    tgt,
                ])
        with open(tgt, 'r') as scene:
            data = scene.read()
            self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
