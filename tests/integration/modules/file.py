# Import python libs
import grp
import os
import sys

# Import salt libs
from saltunittest import skipIf
import integration


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
    def test_chown(self):
        user = os.getlogin()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform == 'linux':
            group = os.getlogin()
        ret = self.run_function('file.chown',
                                arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertTrue(fstat.st_uid, os.getuid())
        self.assertTrue(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_user(self):
        user = 'notanyuseriknow'
        group = os.getlogin()
        ret = self.run_function('file.chown',
                                arg=[self.myfile, user, group])
        self.assertIn('not exist', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_user_no_group(self):
        user = 'notanyuseriknow'
        group = 'notanygroupyoushoulduse'
        ret = self.run_function('file.chown',
                                arg=[self.myfile, user, group])
        self.assertIn('Group does not exist', ret)
        self.assertIn('User does not exist', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_path(self):
        user = os.getlogin()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform == 'linux':
            group = os.getlogin()
        ret = self.run_function('file.chown',
                                arg=['/tmp/nosuchfile', user, group])
        self.assertIn('File not found', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_noop(self):
        user = ''
        group = ''
        ret = self.run_function('file.chown',
                                arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertTrue(fstat.st_uid, os.getuid())
        self.assertTrue(fstat.st_gid, os.getgid())

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

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chgrp_failure(self):
        group = 'thisgroupdoesntexist'
        ret = self.run_function('file.chgrp',
                                arg=[self.myfile, group])
        self.assertIn('not exist', ret)
