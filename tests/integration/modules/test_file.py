import getpass
import os
import shutil
import sys

import pytest
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import requires_system_grains
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

# Posix only
try:
    import grp
    import pwd
except ImportError:
    pass

# Windows only
try:
    import win32file
except ImportError:
    pass


def symlink(source, link_name):
    """
    Handle symlinks on Windows with Python < 3.2
    """
    if salt.utils.platform.is_windows():
        win32file.CreateSymbolicLink(link_name, source)
    else:
        os.symlink(source, link_name)


@pytest.mark.windows_whitelisted
class FileModuleTest(ModuleCase):
    """
    Validate the file module
    """

    def setUp(self):
        self.myfile = os.path.join(RUNTIME_VARS.TMP, "myfile")
        with salt.utils.files.fopen(self.myfile, "w+") as fp:
            fp.write(salt.utils.stringutils.to_str("Hello" + os.linesep))
        self.mydir = os.path.join(RUNTIME_VARS.TMP, "mydir/isawesome")
        if not os.path.isdir(self.mydir):
            # left behind... Don't fail because of this!
            os.makedirs(self.mydir)
        self.mysymlink = os.path.join(RUNTIME_VARS.TMP, "mysymlink")
        if os.path.islink(self.mysymlink) or os.path.isfile(self.mysymlink):
            os.remove(self.mysymlink)
        symlink(self.myfile, self.mysymlink)
        self.mybadsymlink = os.path.join(RUNTIME_VARS.TMP, "mybadsymlink")
        if os.path.islink(self.mybadsymlink) or os.path.isfile(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        symlink("/nonexistentpath", self.mybadsymlink)
        super().setUp()

    def tearDown(self):
        if os.path.isfile(self.myfile):
            os.remove(self.myfile)
        if os.path.islink(self.mysymlink) or os.path.isfile(self.mysymlink):
            os.remove(self.mysymlink)
        if os.path.islink(self.mybadsymlink) or os.path.isfile(self.mybadsymlink):
            os.remove(self.mybadsymlink)
        shutil.rmtree(self.mydir, ignore_errors=True)
        super().tearDown()

    @skipIf(salt.utils.platform.is_windows(), "No security context on Windows")
    @requires_system_grains
    def test_get_selinux_context(self, grains):
        if grains.get("selinux", {}).get("enabled", False):
            NEW_CONTEXT = "system_u:object_r:system_conf_t:s0"
            self.run_function(
                "file.set_selinux_context", arg=[self.myfile, *(NEW_CONTEXT.split(":"))]
            )
            ret_file = self.run_function("file.get_selinux_context", arg=[self.myfile])
            self.assertEqual(ret_file, NEW_CONTEXT)

            # Issue #56557.  Ensure that the context of the directory
            # containing one file is the context of the directory itself, and
            # not the context of the first file in the directory.
            self.run_function(
                "file.set_selinux_context", arg=[self.mydir, *(NEW_CONTEXT.split(":"))]
            )
            ret_dir = self.run_function("file.get_selinux_context", arg=[self.mydir])
            self.assertEqual(ret_dir, NEW_CONTEXT)
            ret_updir = self.run_function(
                "file.get_selinux_context",
                arg=[os.path.abspath(os.path.join(self.mydir, ".."))],
            )
            self.assertNotEqual(ret_updir, NEW_CONTEXT)
        else:
            ret_file = self.run_function("file.get_selinux_context", arg=[self.myfile])
            self.assertIn("No selinux context information is available", ret_file)

    @skipIf(salt.utils.platform.is_windows(), "No security context on Windows")
    @requires_system_grains
    def test_set_selinux_context(self, grains):
        if not grains.get("selinux", {}).get("enabled", False):
            self.skipTest("selinux not available")

        FILE_CONTEXT = "system_u:object_r:system_conf_t:s0"
        ret_file = self.run_function(
            "file.set_selinux_context", arg=[self.myfile, *(FILE_CONTEXT.split(":"))]
        )
        self.assertEqual(ret_file, FILE_CONTEXT)

        DIR_CONTEXT = "system_u:object_r:user_home_t:s0"
        ret_dir = self.run_function(
            "file.set_selinux_context", arg=[self.mydir, *(DIR_CONTEXT.split(":"))]
        )
        self.assertEqual(ret_dir, DIR_CONTEXT)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chown(self):
        user = getpass.getuser()
        if sys.platform == "darwin":
            group = "staff"
        elif sys.platform.startswith(("linux", "freebsd", "openbsd")):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function("file.chown", arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chown_no_user(self):
        user = "notanyuseriknow"
        group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function("file.chown", arg=[self.myfile, user, group])
        self.assertIn("not exist", ret)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chown_no_user_no_group(self):
        user = "notanyuseriknow"
        group = "notanygroupyoushoulduse"
        ret = self.run_function("file.chown", arg=[self.myfile, user, group])
        self.assertIn("Group does not exist", ret)
        self.assertIn("User does not exist", ret)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chown_no_path(self):
        user = getpass.getuser()
        if sys.platform == "darwin":
            group = "staff"
        elif sys.platform.startswith(("linux", "freebsd", "openbsd")):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function("file.chown", arg=["/tmp/nosuchfile", user, group])
        self.assertIn("File not found", ret)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chown_noop(self):
        user = ""
        group = ""
        ret = self.run_function("file.chown", arg=[self.myfile, user, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_uid, os.getuid())
        self.assertEqual(fstat.st_gid, os.getgid())

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chgrp(self):
        if sys.platform == "darwin":
            group = "everyone"
        elif sys.platform.startswith(("linux", "freebsd", "openbsd")):
            group = grp.getgrgid(pwd.getpwuid(os.getuid()).pw_gid).gr_name
        ret = self.run_function("file.chgrp", arg=[self.myfile, group])
        self.assertIsNone(ret)
        fstat = os.stat(self.myfile)
        self.assertEqual(fstat.st_gid, grp.getgrnam(group).gr_gid)

    @skipIf(salt.utils.platform.is_windows(), "No chgrp on Windows")
    def test_chgrp_failure(self):
        group = "thisgroupdoesntexist"
        ret = self.run_function("file.chgrp", arg=[self.myfile, group])
        self.assertIn("not exist", ret)

    def test_patch(self):
        if not self.run_function("cmd.has_exec", ["patch"]):
            self.skipTest("patch is not installed")

        src_patch = os.path.join(RUNTIME_VARS.FILES, "file", "base", "hello.patch")
        src_file = os.path.join(RUNTIME_VARS.TMP, "src.txt")
        with salt.utils.files.fopen(src_file, "w+") as fp:
            fp.write(salt.utils.stringutils.to_str("Hello\n"))

        # dry-run should not modify src_file
        ret = self.minion_run("file.patch", src_file, src_patch, dry_run=True)
        assert ret["retcode"] == 0, repr(ret)
        with salt.utils.files.fopen(src_file) as fp:
            self.assertEqual(salt.utils.stringutils.to_unicode(fp.read()), "Hello\n")

        ret = self.minion_run("file.patch", src_file, src_patch)
        assert ret["retcode"] == 0, repr(ret)
        with salt.utils.files.fopen(src_file) as fp:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(fp.read()), "Hello world\n"
            )

    def test_remove_file(self):
        ret = self.run_function("file.remove", arg=[self.myfile])
        self.assertTrue(ret)

    def test_remove_dir(self):
        ret = self.run_function("file.remove", arg=[self.mydir])
        self.assertTrue(ret)

    def test_remove_symlink(self):
        ret = self.run_function("file.remove", arg=[self.mysymlink])
        self.assertTrue(ret)

    def test_remove_broken_symlink(self):
        ret = self.run_function("file.remove", arg=[self.mybadsymlink])
        self.assertTrue(ret)

    def test_cannot_remove(self):
        ret = self.run_function("file.remove", arg=["tty"])
        self.assertEqual(
            "ERROR executing 'file.remove': File path must be absolute: tty", ret
        )

    def test_source_list_for_single_file_returns_unchanged(self):
        ret = self.run_function(
            "file.source_list", ["salt://http/httpd.conf", "filehash", "base"]
        )
        self.assertEqual(list(ret), ["salt://http/httpd.conf", "filehash"])

    def test_source_list_for_single_local_file_slash_returns_unchanged(self):
        ret = self.run_function("file.source_list", [self.myfile, "filehash", "base"])
        self.assertEqual(list(ret), [self.myfile, "filehash"])

    def test_source_list_for_single_local_file_proto_returns_unchanged(self):
        ret = self.run_function(
            "file.source_list", ["file://" + self.myfile, "filehash", "base"]
        )
        self.assertEqual(list(ret), ["file://" + self.myfile, "filehash"])

    def test_source_list_for_multiple_files_with_missing_files(self):
        file_list = [
            "salt://does/not/exist",
            "file://" + self.myfile,
            "http://localhost//does/not/exist",
            "salt://http/httpd.conf",
        ]
        ret = self.run_function("file.source_list", [file_list, "filehash", "base"])
        self.assertEqual(list(ret), ["file://" + self.myfile, "filehash"])

    def test_source_list_for_multiple_files_dict_with_missing_files(self):
        file_list = [
            {"salt://does/not/exist": "filehash"},
            {"file://" + self.myfile: "filehash"},
            {"http://localhost//does/not/exist": "filehash"},
            {"salt://http/httpd.conf": "filehash"},
        ]
        ret = self.run_function("file.source_list", [file_list, "", "base"])
        self.assertEqual(list(ret), ["file://" + self.myfile, "filehash"])

    def test_file_line_changes_format(self):
        """
        Test file.line changes output formatting.

        Issue #41474
        """
        ret = self.minion_run(
            "file.line", self.myfile, "Goodbye", mode="insert", after="Hello"
        )
        self.assertIn("Hello" + os.linesep + "+Goodbye", ret)

    def test_file_line_changes_entire_line(self):
        """
        Test file.line entire line matching

        Issue #49855
        """
        ret = self.minion_run(
            "file.line", self.myfile, "Goodbye", mode="insert", after="Hello"
        )
        assert "Hello" + os.linesep + "+Goodbye" in ret

        ret = self.minion_run(
            "file.line", self.myfile, "Goodbye 1", mode="insert", after="Hello"
        )
        assert (
            "Hello" + os.linesep + "+Goodbye 1" + os.linesep + " Goodbye" + os.linesep
            in ret
        )

        with salt.utils.files.fopen(self.myfile, "r") as fh_:
            content = fh_.read()

        assert (
            "Hello" + os.linesep + "Goodbye 1" + os.linesep + "Goodbye" + os.linesep
            == content
        )

    def test_file_line_content(self):
        self.minion_run(
            "file.line", self.myfile, "Goodbye", mode="insert", after="Hello"
        )
        with salt.utils.files.fopen(self.myfile, "r") as fp:
            content = fp.read()
        self.assertEqual(content, "Hello" + os.linesep + "Goodbye" + os.linesep)

    def test_file_line_duplicate_insert_after(self):
        """
        Test file.line duplicates line.

        Issue #50254
        """
        with salt.utils.files.fopen(self.myfile, "a") as fp:
            fp.write(salt.utils.stringutils.to_str("Goodbye" + os.linesep))
        self.minion_run(
            "file.line", self.myfile, "Goodbye", mode="insert", after="Hello"
        )
        with salt.utils.files.fopen(self.myfile, "r") as fp:
            content = fp.read()
        self.assertEqual(content, "Hello" + os.linesep + "Goodbye" + os.linesep)

    def test_file_line_duplicate_insert_before(self):
        """
        Test file.line duplicates line.

        Issue #50254
        """
        with salt.utils.files.fopen(self.myfile, "a") as fp:
            fp.write(salt.utils.stringutils.to_str("Goodbye" + os.linesep))
        self.minion_run(
            "file.line", self.myfile, "Hello", mode="insert", before="Goodbye"
        )
        with salt.utils.files.fopen(self.myfile, "r") as fp:
            content = fp.read()
        self.assertEqual(content, "Hello" + os.linesep + "Goodbye" + os.linesep)

    def test_file_line_duplicate_ensure_after(self):
        """
        Test file.line duplicates line.

        Issue #50254
        """
        with salt.utils.files.fopen(self.myfile, "a") as fp:
            fp.write(salt.utils.stringutils.to_str("Goodbye" + os.linesep))
        self.minion_run(
            "file.line", self.myfile, "Goodbye", mode="ensure", after="Hello"
        )
        with salt.utils.files.fopen(self.myfile, "r") as fp:
            content = fp.read()
        self.assertEqual(content, "Hello" + os.linesep + "Goodbye" + os.linesep)

    def test_file_line_duplicate_ensure_before(self):
        """
        Test file.line duplicates line.

        Issue #50254
        """
        with salt.utils.files.fopen(self.myfile, "a") as fp:
            fp.write(salt.utils.stringutils.to_str("Goodbye" + os.linesep))
        self.minion_run(
            "file.line", self.myfile, "Hello", mode="ensure", before="Goodbye"
        )
        with salt.utils.files.fopen(self.myfile, "r") as fp:
            content = fp.read()
        self.assertEqual(content, "Hello" + os.linesep + "Goodbye" + os.linesep)

    def test_file_read_bytes(self):
        """
        Test that ``file.read`` reads and returns ``bytes`` data
        """
        # Write some random bytes
        data = b"n\x1a\xf7S@tBI\xa9J"
        with salt.utils.files.fopen(self.myfile, "wb") as fp:
            fp.write(data)

        ret = self.minion_run("file.read", self.myfile, binary=True)
        self.assertEqual(type(ret), bytes)
        self.assertEqual(ret, data)

    def test_file_read_str(self):
        """
        Test that ``file.read`` reads and returns ``str`` data
        """
        # Write some str data
        data = "printable characters"
        with salt.utils.files.fopen(self.myfile, "w") as fp:
            fp.write(data)

        ret = self.minion_run("file.read", self.myfile)
        self.assertEqual(type(ret), str)
        self.assertEqual(ret, data)
