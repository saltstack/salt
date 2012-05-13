'''
Tests for the file state
'''
# Import python libs
import os
#
# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon

class FileTest(integration.ModuleCase):
    '''
    Validate the file state
    '''
    def test_symlink(self):
        '''
        file.symlink
        '''
        name = os.path.join(integration.TMP, 'symlink')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', name=name, target=tgt)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_symlink(self):
        '''
        file.symlink test interface
        '''
        name = os.path.join(integration.TMP, 'symlink')
        tgt = os.path.join(integration.TMP, 'target')
        ret = self.run_state('file.symlink', test=True, name=name, target=tgt)
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

    def test_absent_file(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with open(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.isfile(name))

    def test_absent_dir(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'dir_to_kill')
        os.makedirs(name)
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.isdir(name))
    
    def test_absent_link(self):
        '''
        file.absent
        '''
        name = os.path.join(integration.TMP, 'link_to_kill')
        os.symlink(name, '{0}.tgt'.format(name))
        ret = self.run_state('file.absent', name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
        self.assertFalse(os.path.islink(name))

    def test_test_absent(self):
        '''
        file.absent test interface
        '''
        name = os.path.join(integration.TMP, 'file_to_kill')
        with open(name, 'w+') as fp_:
            fp_.write('killme')
        ret = self.run_state('file.absent', test=True, name=name)
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)
        self.assertTrue(os.path.isfile(name))

    def test_managed(self):
        '''
        file.managed
        '''
        name = os.path.join(integration.TMP, 'grail_scene33')
        ret = self.run_state(
                'file.managed',
                name=name,
                source='salt://grail/scene33')
        src = os.path.join(
                integration.FILES,
                'file',
                'base',
                'grail',
                'scene33'
                )
        with open(src, 'r') as fp_:
            master_data = fp_.read()
        with open(name, 'r') as fp_:
            minion_data = fp_.read()
        self.assertEqual(master_data, minion_data)
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_managed(self):
        '''
        file.managed test interface
        '''
        name = os.path.join(integration.TMP, 'grail_not_scene33')
        ret = self.run_state(
                'file.managed',
                test=True,
                name=name,
                source='salt://grail/scene33')
        self.assertFalse(os.path.isfile(name))
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

    def test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(integration.TMP, 'a_new_dir')
        ret = self.run_state(
                'file.directory',
                name=name,
                )
        self.assertTrue(os.path.isdir(name))
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_directory(self):
        '''
        file.directory
        '''
        name = os.path.join(integration.TMP, 'a_not_dir')
        ret = self.run_state(
                'file.directory',
                test=True,
                name=name,
                )
        self.assertFalse(os.path.isdir(name))
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

    def test_recurse(self):
        '''
        file.recurse
        '''
        name = os.path.join(integration.TMP, 'recurse_dir')
        ret = self.run_state(
                'file.recurse',
                name=name,
                source='salt://grail',
                )
        self.assertTrue(os.path.isfile(os.path.join(name, '36', 'scene')))
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_recurse(self):
        '''
        file.recurse test interface
        '''
        name = os.path.join(integration.TMP, 'recurse_test_dir')
        ret = self.run_state(
                'file.recurse',
                test=True,
                name=name,
                source='salt://grail',
                )
        self.assertFalse(os.path.isfile(os.path.join(name, '36', 'scene')))
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

    def test_sed(self):
        '''
        file.sed
        '''
        name = os.path.join(integration.TMP, 'sed_test')
        with open(name, 'w+') as fp_:
            fp_.write('change_me')
        ret = self.run_state(
                'file.sed',
                name=name,
                before='change',
                after='salt'
                )
        with open(name, 'r') as fp_:
            self.assertIn('salt', fp_.read())
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)

    def test_test_sed(self):
        '''
        file.sed test integration
        '''
        name = os.path.join(integration.TMP, 'sed_test_test')
        with open(name, 'w+') as fp_:
            fp_.write('change_me')
        ret = self.run_state(
                'file.sed',
                test=True,
                name=name,
                before='change',
                after='salt'
                )
        with open(name, 'r') as fp_:
            self.assertIn('change', fp_.read())
        result = ret[ret.keys()[0]]['result']
        self.assertIsNone(result)

    def test_comment(self):
        '''
        file.comment
        '''
        name = os.path.join(integration.TMP, 'comment_test')
        with open(name, 'w+') as fp_:
            fp_.write('comment_me')
        ret = self.run_state(
                'file.comment',
                name=name,
                regex='.*comment.*',
                )
        with open(name, 'r') as fp_:
            self.assertIn('#comment', fp_.read())
        result = ret[ret.keys()[0]]['result']
        self.assertTrue(result)
