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
            self.assertNotIn('bacon', data)

    def test_get_template(self):
        '''
        cp.get_template
        '''
        tgt = os.path.join(integration.TMP, 'scene33')
        self.run_function(
                'cp.get_template',
                [
                    'salt://grail/scene33',
                    tgt,
                    'spam=bacon',
                ])
        with open(tgt, 'r') as scene:
            data = scene.read()
            self.assertIn('bacon', data)
            self.assertNotIn('spam', data)

    def test_get_dir(self):
        '''
        cp.get_dir
        '''
        tgt = os.path.join(integration.TMP, 'many')
        self.run_function(
                'cp.get_dir',
                [
                    'salt://grail',
                    tgt
                ])
        self.assertIn('grail', os.listdir(tgt))
        self.assertIn('36', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('empty', os.listdir(os.path.join(tgt, 'grail')))
        self.assertIn('scene', os.listdir(os.path.join(tgt, 'grail', '36')))

    def test_get_url(self):
        '''
        cp.get_url
        '''
        # We should add a "if the internet works download some files"
        tgt = os.path.join(integration.TMP, 'scene33')
        self.run_function(
                'cp.get_url',
                [
                    'salt://grail/scene33',
                    tgt,
                ])
        with open(tgt, 'r') as scene:
            data = scene.read()
            self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
            self.assertNotIn('bacon', data)

    def test_cache_file(self):
        '''
        cp.cache_file
        '''
        ret = self.run_function(
                'cp.cache_file',
                [
                    'salt://grail/scene33',
                ])
        with open(ret, 'r') as scene:
            data = scene.read()
            self.assertIn('KNIGHT:  They\'re nervous, sire.', data)
            self.assertNotIn('bacon', data)

    def test_cache_files(self):
        '''
        cp.cache_files
        '''
        ret = self.run_function(
                'cp.cache_files',
                [
                    ['salt://grail/scene33' ,'salt://grail/36/scene'],
                ])
        for path in ret:
            with open(path, 'r') as scene:
                data = scene.read()
                self.assertIn('ARTHUR:', data)
                self.assertNotIn('bacon', data)

    def test_cache_master(self):
        '''
        cp.cache_master
        '''
        ret = self.run_function(
                'cp.cache_master',
                )
        for path in ret:
            self.assertTrue(os.path.exists(path))

    def test_cache_local_file(self):
        '''
        cp.cache_local_file
        '''
        src = os.path.join(integration.TMP, 'random')
        with open(src, 'w+') as fn_:
            fn_.write('foo')
        ret = self.run_function(
                'cp.cache_local_file',
                [src])
        with open(ret, 'r') as cp_:
            self.assertEqual(cp_.read(), 'foo')

    def test_list_states(self):
        '''
        cp.list_states
        '''
        ret = self.run_function(
                'cp.list_states',
                )
        self.assertIn('core', ret)
        self.assertIn('top', ret)
