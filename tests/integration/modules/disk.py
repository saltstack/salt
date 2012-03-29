# Import python libs
import os

# Import salt libs
import integration

class DiskModuleTest(integration.ModuleCase):
    '''
    Validate the disk module
    '''
    def test_usage(self):
        '''
        disk.usage
        '''
        ret = self.run_function('disk.usage')
        self.assertTrue(isinstance(ret, dict))
        if not isinstance(ret, dict):
            return
        for key, val in ret.items():
            self.assertTrue('filesystem' in val)
            self.assertTrue('1K-blocks' in val)
            self.assertTrue('used' in val)
            self.assertTrue('available' in val)
            self.assertTrue('capacity' in val)

    def test_inodeusage(self):
        '''
        disk.inodeusage
        '''
        ret = self.run_function('disk.inodeusage')
        self.assertTrue(isinstance(ret, dict))
        if not isinstance(ret, dict):
            return
        for key, val in ret.items():
            self.assertTrue('inodes' in val)
            self.assertTrue('used' in val)
            self.assertTrue('free' in val)
            self.assertTrue('use' in val)
            self.assertTrue('filesystem' in val)

