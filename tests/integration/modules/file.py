# Import python libs
import getpass
import grp
import os
import shutil
import sys

# Import salt libs
import salt.utils
import integration
from saltunittest import skipIf


class FileModuleTest(integration.ModuleCase):
    '''
    Validate the file module
    '''
    def setUp(self):
        self.myfile = os.path.join(integration.TMP, 'myfile')
        with salt.utils.fopen(self.myfile, 'w+') as fp:
            fp.write("Hello\n")
        self.mydir = os.path.join(integration.TMP, 'mydir/isawesome')
        if not os.path.isdir(self.mydir):
            # left behind... Don't fail because of this!
            os.makedirs(self.mydir)
        self.mysymlink = os.path.join(integration.TMP, 'mysymlink')
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        os.symlink(self.myfile, self.mysymlink)
        self.mybadsymlink = os.path.join(integration.TMP, 'mybadsymlink')
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        os.symlink('/nonexistantpath', self.mybadsymlink)
        super(FileModuleTest, self).setUp()

    def tearDown(self):
        os.remove(self.myfile)
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        shutil.rmtree(self.mydir, ignore_errors=True)
        super(FileModuleTest, self).tearDown()

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown(self):
        user = getpass.getuser()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform.startswith('linux'):
            group = getpass.getuser()
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_user(self):
        user = 'notanyuseriknow'
        group = getpass.getuser()
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIn('not exist', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_user_no_group(self):
        user = 'notanyuseriknow'
        group = 'notanygroupyoushoulduse'
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIn('Group does not exist', ret)
        self.assertIn('User does not exist', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_no_path(self):
        user = getpass.getuser()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform.startswith('linux'):
            group = getpass.getuser()
        ret = self.run_function('file.chown',
                                arg=['/tmp/nosuchfile', user, group])
        self.assertIn('File not found', ret)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chown_noop(self):
        user = ''
        group = ''
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, os.getgid())

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chgrp(self):
        if sys.platform == 'darwin':
            group = 'everyone'
        elif sys.platform.startswith('linux'):
            group = getpass.getuser()
        ret = self.run_function('file.chgrp', arg=[self.myfile, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(sys.platform.startswith('win'), 'No chgrp on Windows')
    def test_chgrp_failure(self):
        group = 'thisgroupdoesntexist'
        ret = self.run_function('file.chgrp', arg=[self.myfile, group])
        self.assertIn('not exist', ret)

    def test_patch(self):
        if not self.run_function('cmd.has_exec', ['patch']):
            self.skipTest('patch is not installed')

        src_patch = os.path.join(
            integration.FILES, 'file', 'base', 'hello.patch')
        src_file = os.path.join(integration.TMP, 'src.txt')
        with salt.utils.fopen(src_file, 'w+') as fp:
            fp.write("Hello\n")

        # dry-run should not modify src_file
        ret = self.minion_run('file.patch', src_file, src_patch, dry_run=True)
        assert ret['retcode'] == 0, repr(ret)
        with salt.utils.fopen(src_file) as fp:
            self.assertEqual(fp.read(), 'Hello\n')

        ret = self.minion_run('file.patch', src_file, src_patch)
        assert ret['retcode'] == 0, repr(ret)
        with salt.utils.fopen(src_file) as fp:
            self.assertEqual(fp.read(), 'Hello world\n')

    def test_remove_file(self):
        ret = self.run_function('file.remove', args=[self.myfile])
        self.assertTrue(ret)

    def test_remove_dir(self):
        ret = self.run_function('file.remove', args=[self.mydir])
        self.assertTrue(ret)

    def test_remove_symlink(self):
        ret = self.run_function('file.remove', args=[self.mysymlink])
        self.assertTrue(ret)

    def test_remove_broken_symlink(self):
        ret = self.run_function('file.remove', args=[self.mybadsymlink])
        self.assertTrue(ret)

    def test_cannot_remove(self):
        ret = self.run_function('file.remove', args=['/dev/tty'])
        self.assertEqual(
            'ERROR executing file.remove: File path must be absolute.', ret
        )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileModuleTest)
