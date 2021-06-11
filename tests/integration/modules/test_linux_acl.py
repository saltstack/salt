import os
import shutil

import pytest
import salt.utils.files
import salt.utils.user
from tests.support.case import ModuleCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

# Doesn't work. Why?
# @requires_salt_modules('acl')
# @requires_salt_modules('linux_acl')
# Acl package should be installed to test linux_acl module


@pytest.mark.skip_if_binaries_missing("getfacl")
@pytest.mark.windows_whitelisted
class LinuxAclModuleTest(ModuleCase, AdaptedConfigurationTestCaseMixin):
    """
    Validate the linux_acl module
    """

    def setUp(self):
        # Blindly copied from tests.integration.modules.file; Refactoring?
        self.myfile = os.path.join(RUNTIME_VARS.TMP, "myfile")
        with salt.utils.files.fopen(self.myfile, "w+") as fp:
            fp.write("Hello\n")
        self.mydir = os.path.join(RUNTIME_VARS.TMP, "mydir/isawesome")
        if not os.path.isdir(self.mydir):
            # left behind... Don't fail because of this!
            os.makedirs(self.mydir)
        self.mysymlink = os.path.join(RUNTIME_VARS.TMP, "mysymlink")
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        os.symlink(self.myfile, self.mysymlink)
        self.mybadsymlink = os.path.join(RUNTIME_VARS.TMP, "mybadsymlink")
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        os.symlink("/nonexistentpath", self.mybadsymlink)
        super().setUp()

    def tearDown(self):
        if os.path.isfile(self.myfile):
            os.remove(self.myfile)
        if os.path.islink(self.mysymlink):
            os.remove(self.mysymlink)
        if os.path.islink(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        shutil.rmtree(self.mydir, ignore_errors=True)
        super().tearDown()

    @skipIf(salt.utils.platform.is_freebsd(), "Skip on FreeBSD")
    def test_version(self):
        self.assertRegex(self.run_function("acl.version"), r"\d+\.\d+\.\d+")

    @skipIf(salt.utils.platform.is_freebsd(), "Skip on FreeBSD")
    def test_getfacl_w_single_file_without_acl(self):
        ret = self.run_function("acl.getfacl", arg=[self.myfile])
        user = salt.utils.user.get_user()
        group = salt.utils.user.get_default_group(user)
        self.maxDiff = None
        self.assertEqual(
            ret,
            {
                self.myfile: {
                    "other": [
                        {
                            "": {
                                "octal": 4,
                                "permissions": {
                                    "read": True,
                                    "write": False,
                                    "execute": False,
                                },
                            }
                        }
                    ],
                    "user": [
                        {
                            user: {
                                "octal": 6,
                                "permissions": {
                                    "read": True,
                                    "write": True,
                                    "execute": False,
                                },
                            }
                        }
                    ],
                    "group": [
                        {
                            group: {
                                "octal": 4,
                                "permissions": {
                                    "read": True,
                                    "write": False,
                                    "execute": False,
                                },
                            }
                        }
                    ],
                    "comment": {"owner": user, "group": group, "file": self.myfile},
                }
            },
        )
