# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import getpass
import grp
import pwd
import os
import shutil
import sys

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.mock import patch, MagicMock

# Import salt libs
import salt.utils
from salt.modules import file as filemod


class FileModuleTest(integration.ModuleCase):
    '''
    Validate the file module
    '''
    def setUp(self):
        self.myfile = os.path.join(integration.TMP, 'myfile')
        with salt.utils.fopen(self.myfile, 'w+') as fp:
            fp.write('Hello\n')
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
        os.symlink('/nonexistentpath', self.mybadsymlink)
        super(FileModuleTest, self).setUp()

    def tearDown(self):
        if os.path.isfile(self.myfile):
            os.remove(self.myfile)
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        shutil.rmtree(self.mydir, ignore_errors=True)
        super(FileModuleTest, self).tearDown()

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chown(self):
        user = getpass.getuser()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform.startswith(('linux', 'freebsd', 'openbsd')):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chown_no_user(self):
        user = 'notanyuseriknow'
        group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIn('not exist', ret)

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chown_no_user_no_group(self):
        user = 'notanyuseriknow'
        group = 'notanygroupyoushoulduse'
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIn('Group does not exist', ret)
        self.assertIn('User does not exist', ret)

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chown_no_path(self):
        user = getpass.getuser()
        if sys.platform == 'darwin':
            group = 'staff'
        elif sys.platform.startswith(('linux', 'freebsd', 'openbsd')):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function('file.chown',
                                arg=['/tmp/nosuchfile', user, group])
        self.assertIn('File not found', ret)

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chown_noop(self):
        user = ''
        group = ''
        ret = self.run_function('file.chown', arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, os.getgid())

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
    def test_chgrp(self):
        if sys.platform == 'darwin':
            group = 'everyone'
        elif sys.platform.startswith(('linux', 'freebsd', 'openbsd')):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function('file.chgrp', arg=[self.myfile, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(salt.utils.is_windows(), 'No chgrp on Windows')
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
            fp.write('Hello\n')

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
        ret = self.run_function('file.remove', arg=[self.myfile])
        self.assertTrue(ret)

    def test_remove_dir(self):
        ret = self.run_function('file.remove', arg=[self.mydir])
        self.assertTrue(ret)

    def test_remove_symlink(self):
        ret = self.run_function('file.remove', arg=[self.mysymlink])
        self.assertTrue(ret)

    def test_remove_broken_symlink(self):
        ret = self.run_function('file.remove', arg=[self.mybadsymlink])
        self.assertTrue(ret)

    def test_cannot_remove(self):
        ret = self.run_function('file.remove', arg=['tty'])
        self.assertEqual(
            'ERROR executing \'file.remove\': File path must be absolute: tty', ret
        )

    def test_source_list_for_single_file_returns_unchanged(self):
        ret = self.run_function('file.source_list', ['salt://http/httpd.conf',
                                                     'filehash', 'base'])
        self.assertEqual(list(ret), ['salt://http/httpd.conf', 'filehash'])

    def test_source_list_for_list_returns_existing_file(self):
        filemod.__salt__ = {
            'cp.list_master': MagicMock(
                return_value=['http/httpd.conf.fallback']),
            'cp.list_master_dirs': MagicMock(return_value=[]),
        }
        filemod.__context__ = {}

        ret = filemod.source_list(['salt://http/httpd.conf',
                                   'salt://http/httpd.conf.fallback'],
                                  'filehash', 'base')
        self.assertEqual(list(ret), ['salt://http/httpd.conf.fallback', 'filehash'])

    def test_source_list_for_list_returns_file_from_other_env(self):
        def list_master(env):
            dct = {'base': [], 'dev': ['http/httpd.conf']}
            return dct[env]
        filemod.__salt__ = {
            'cp.list_master': MagicMock(side_effect=list_master),
            'cp.list_master_dirs': MagicMock(return_value=[]),
        }
        filemod.__context__ = {}

        ret = filemod.source_list(['salt://http/httpd.conf?saltenv=dev',
                                   'salt://http/httpd.conf.fallback'],
                                  'filehash', 'base')
        self.assertEqual(list(ret), ['salt://http/httpd.conf?saltenv=dev', 'filehash'])

    def test_source_list_for_list_returns_file_from_dict(self):
        filemod.__salt__ = {
            'cp.list_master': MagicMock(return_value=['http/httpd.conf']),
            'cp.list_master_dirs': MagicMock(return_value=[]),
        }
        filemod.__context__ = {}

        ret = filemod.source_list(
            [{'salt://http/httpd.conf': ''}], 'filehash', 'base')
        self.assertEqual(list(ret), ['salt://http/httpd.conf', 'filehash'])

    @patch('salt.modules.file.os.remove')
    def test_source_list_for_list_returns_file_from_dict_via_http(self, remove):
        remove.return_value = None
        filemod.__salt__ = {
            'cp.list_master': MagicMock(return_value=[]),
            'cp.list_master_dirs': MagicMock(return_value=[]),
            'cp.cache_file': MagicMock(return_value='/tmp/http.conf'),
        }
        filemod.__context__ = {}

        ret = filemod.source_list(
            [{'http://t.est.com/http/httpd.conf': 'filehash'}], '', 'base')
        self.assertEqual(list(ret), ['http://t.est.com/http/httpd.conf', 'filehash'])

    def test_source_list_for_single_local_file_slash_returns_unchanged(self):
        ret = self.run_function('file.source_list', [self.myfile,
                                                     'filehash', 'base'])
        self.assertEqual(list(ret), [self.myfile, 'filehash'])

    def test_source_list_for_single_local_file_proto_returns_unchanged(self):
        ret = self.run_function('file.source_list', ['file://' + self.myfile,
                                                     'filehash', 'base'])
        self.assertEqual(list(ret), ['file://' + self.myfile, 'filehash'])

    def test_source_list_for_list_returns_existing_local_file_slash(self):
        ret = filemod.source_list([self.myfile + '-foo',
                                   self.myfile],
                                  'filehash', 'base')
        self.assertEqual(list(ret), [self.myfile, 'filehash'])

    def test_source_list_for_list_returns_existing_local_file_proto(self):
        ret = filemod.source_list(['file://' + self.myfile + '-foo',
                                   'file://' + self.myfile],
                                  'filehash', 'base')
        self.assertEqual(list(ret), ['file://' + self.myfile, 'filehash'])

    def test_source_list_for_list_returns_local_file_slash_from_dict(self):
        ret = filemod.source_list(
            [{self.myfile: ''}], 'filehash', 'base')
        self.assertEqual(list(ret), [self.myfile, 'filehash'])

    def test_source_list_for_list_returns_local_file_proto_from_dict(self):
        ret = filemod.source_list(
            [{'file://' + self.myfile: ''}], 'filehash', 'base')
        self.assertEqual(list(ret), ['file://' + self.myfile, 'filehash'])
