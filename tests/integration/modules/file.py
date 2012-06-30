# Import python libs
import grp
import os
import sys

# Import salt libs
from saltunittest import skipIf, TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class FileModuleTest(integration.ModuleCase):
    '''
    Validate the file module
    '''
    def setUp(self):
        self.myfile = os.path.join(integration.TMP, 'myfile')
        with open(self.myfile, 'w+') as fp:
            fp.write("Hello\n")
        super(FileModuleTest, self).setUp()

    def tearDown(self):
        os.remove(self.myfile)
        super(FileModuleTest, self).tearDown()

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chgrp(self):
        if sys.platform == 'darwin':
            group = 'everyone'
        elif sys.platform == 'linux':
            group = os.getlogin()
        ret = self.run_function('file.chgrp',
                                arg=[self.myfile, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertTrue(fstat.st_gid, grp.getgrnam(group).gr_gid)
