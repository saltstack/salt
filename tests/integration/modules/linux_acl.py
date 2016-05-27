# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, skip_if_binaries_missing
import salt.utils
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
# from salt.modules import linux_acl as acl


# Acl package should be installed to test linux_acl module
@skip_if_binaries_missing(['getfacl'])
# Doesn't work. Why?
# @requires_salt_modules('acl')
# @requires_salt_modules('linux_acl')
class LinuxAclModuleTest(integration.ModuleCase,
                         integration.AdaptedConfigurationTestCaseMixIn):
    '''
    Validate the linux_acl module
    '''
    def setUp(self):
        # Blindly copied from tests.integration.modules.file; Refactoring?
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
        super(LinuxAclModuleTest, self).setUp()

    def tearDown(self):
        if os.path.isfile(self.myfile):
            os.remove(self.myfile)
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        shutil.rmtree(self.mydir, ignore_errors=True)
        super(LinuxAclModuleTest, self).tearDown()

    def test_version(self):
        self.assertRegexpMatches(self.run_function('acl.version'), r'\d+\.\d+\.\d+')

    def test_getfacl_w_single_file_without_acl(self):
        ret = self.run_function('acl.getfacl', arg=[self.myfile])
        self.maxDiff = None
        self.assertEqual(
            ret,
            {self.myfile: {'other': [{'': {'octal': 4, 'permissions': {'read': True, 'write': False, 'execute': False}}}],
                           'user': [{'root': {'octal': 6, 'permissions': {'read': True, 'write': True, 'execute': False}}}],
                           'group': [{'root': {'octal': 4, 'permissions': {'read': True, 'write': False, 'execute': False}}}],
                           'comment': {'owner': 'root', 'group': 'root', 'file': self.myfile}}}
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LinuxAclModuleTest)
