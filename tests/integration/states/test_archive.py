"""
Tests for the archive state
"""

import errno
import logging
import os

import pytest

import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import Webserver
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

# Setup logging
log = logging.getLogger(__name__)

ARCHIVE_DIR = (
    os.path.join("c:/", "tmp") if salt.utils.platform.is_windows() else "/tmp/archive"
)

ARCHIVE_NAME = "custom.tar.gz"
ARCHIVE_TAR_SOURCE = f"http://localhost:{9999}/{ARCHIVE_NAME}"
ARCHIVE_TAR_HASH = "md5=7643861ac07c30fe7d2310e9f25ca514"
ARCHIVE_TAR_SHA_HASH = (
    "sha256=9591159d86f0a180e4e0645b2320d0235e23e66c66797df61508bf185e0ac1d2"
)
ARCHIVE_TAR_BAD_HASH = "md5=d41d8cd98f00b204e9800998ecf8427e"
ARCHIVE_TAR_HASH_UPPER = "md5=7643861AC07C30FE7D2310E9F25CA514"


class ArchiveTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the archive state
    """

    @classmethod
    def setUpClass(cls):
        cls.webserver = Webserver()
        cls.webserver.start()
        cls.archive_tar_source = cls.webserver.url("custom.tar.gz")
        cls.archive_local_tar_source = "file://{}".format(
            os.path.join(RUNTIME_VARS.BASE_FILES, ARCHIVE_NAME)
        )
        cls.untar_file = os.path.join(ARCHIVE_DIR, "custom/README")

    @classmethod
    def tearDownClass(cls):
        cls.webserver.stop()

    def setUp(self):
        self._clear_archive_dir()

    def tearDown(self):
        self._clear_archive_dir()
        try:
            salt.utils.files.rm_rf(
                os.path.join(RUNTIME_VARS.TMP_ROOT_DIR, "cache", "archive_hash")
            )
        except OSError:
            # some tests do notcreate the archive_hash directory
            pass

    @staticmethod
    def _clear_archive_dir():
        try:
            salt.utils.files.rm_rf(ARCHIVE_DIR)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

    def _check_extracted(self, path):
        """
        function to check if file was extracted
        """
        log.debug("Checking for extracted file: %s", path)
        self.assertTrue(os.path.isfile(path))

    def run_function(self, *args, **kwargs):  # pylint: disable=arguments-differ
        ret = super().run_function(*args, **kwargs)
        log.debug("ret = %s", ret)
        return ret

    def run_state(self, *args, **kwargs):  # pylint: disable=arguments-differ
        ret = super().run_state(*args, **kwargs)
        log.debug("ret = %s", ret)
        return ret

    def test_archive_extracted_skip_verify(self):
        """
        test archive.extracted with skip_verify
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            archive_format="tar",
            skip_verify=True,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")
        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_with_source_hash(self):
        """
        test archive.extracted without skip_verify
        only external resources work to check to
        ensure source_hash is verified correctly
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_HASH,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.skip_if_not_root
    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_with_root_user_and_group(self):
        """
        test archive.extracted with user and group set to "root"
        """
        r_group = "root"
        if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
            r_group = "wheel"
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_HASH,
            user="root",
            group=r_group,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.slow_test
    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_with_strip_in_options(self):
        """
        test archive.extracted with --strip in options
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            source_hash=ARCHIVE_TAR_HASH,
            options="--strip=1",
            enforce_toplevel=False,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")

        self.assertSaltTrueReturn(ret)

        self._check_extracted(os.path.join(ARCHIVE_DIR, "README"))

    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_with_strip_components_in_options(self):
        """
        test archive.extracted with --strip-components in options
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            source_hash=ARCHIVE_TAR_HASH,
            options="--strip-components=1",
            enforce_toplevel=False,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")

        self.assertSaltTrueReturn(ret)

        self._check_extracted(os.path.join(ARCHIVE_DIR, "README"))

    @pytest.mark.slow_test
    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_without_archive_format(self):
        """
        test archive.extracted with no archive_format option
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            source_hash=ARCHIVE_TAR_HASH,
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")
        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.skip_on_fips_enabled_platform
    def test_archive_extracted_with_cmd_unzip_false(self):
        """
        test archive.extracted using use_cmd_unzip argument as false
        """

        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_tar_source,
            source_hash=ARCHIVE_TAR_HASH,
            use_cmd_unzip=False,
            archive_format="tar",
        )
        if "Timeout" in ret:
            self.skipTest("Timeout talking to local tornado server.")
        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    def test_local_archive_extracted(self):
        """
        test archive.extracted with local file
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.skip_on_fips_enabled_platform
    def test_local_archive_extracted_skip_verify(self):
        """
        test archive.extracted with local file, bad hash and skip_verify
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_BAD_HASH,
            skip_verify=True,
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.slow_test
    @pytest.mark.skip_on_fips_enabled_platform
    def test_local_archive_extracted_with_source_hash(self):
        """
        test archive.extracted with local file and valid hash
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_HASH,
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.slow_test
    @pytest.mark.skip_on_fips_enabled_platform
    def test_local_archive_extracted_with_bad_source_hash(self):
        """
        test archive.extracted with local file and bad hash
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_BAD_HASH,
        )

        self.assertSaltFalseReturn(ret)

    @pytest.mark.skip_on_fips_enabled_platform
    def test_local_archive_extracted_with_uppercase_source_hash(self):
        """
        test archive.extracted with local file and bad hash
        """
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            source_hash=ARCHIVE_TAR_HASH_UPPER,
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

    @pytest.mark.slow_test
    def test_archive_extracted_with_non_base_saltenv(self):
        """
        test archive.extracted with a saltenv other than `base`
        """
        ret = self.run_function(
            "state.sls",
            ["issue45893"],
            pillar={"issue45893.name": ARCHIVE_DIR},
            saltenv="prod",
        )
        self.assertSaltTrueReturn(ret)
        self._check_extracted(os.path.join(ARCHIVE_DIR, self.untar_file))

    @pytest.mark.slow_test
    def test_local_archive_extracted_with_skip_files_list_verify(self):
        """
        test archive.extracted with local file and skip_files_list_verify set to True
        """
        expected_comment = (
            "existing source sum is the same as the expected one and "
            "skip_files_list_verify argument was set to True. "
            "Extraction is not needed"
        )

        # Clearing the minion cache at the start to ensure that different tests of
        # skip_files_list_verify won't affect each other
        self.run_function("saltutil.clear_cache")
        self.run_function("saltutil.sync_all")

        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            skip_files_list_verify=True,
            source_hash_update=True,
            keep_source=True,
            source_hash=ARCHIVE_TAR_SHA_HASH,
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            skip_files_list_verify=True,
            source_hash_update=True,
            keep_source=True,
            source_hash=ARCHIVE_TAR_SHA_HASH,
        )

        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(expected_comment, ret)

    def test_local_archive_extracted_with_skip_files_list_verify_and_keep_source_is_false(
        self,
    ):
        """
        test archive.extracted with local file and skip_files_list_verify set to True
        and keep_source is set to False.
        """
        expected_comment = (
            "existing source sum is the same as the expected one and "
            "skip_files_list_verify argument was set to True. "
            "Extraction is not needed"
        )
        # Clearing the minion cache at the start to ensure that different tests of
        # skip_files_list_verify won't affect each other
        self.run_function("saltutil.clear_cache")
        self.run_function("saltutil.sync_all")

        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            skip_files_list_verify=True,
            source_hash_update=True,
            keep_source=False,
            source_hash=ARCHIVE_TAR_SHA_HASH,
        )

        self.assertSaltTrueReturn(ret)

        self._check_extracted(self.untar_file)

        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            skip_files_list_verify=True,
            source_hash_update=True,
            keep_source=False,
            source_hash=ARCHIVE_TAR_SHA_HASH,
        )

        self.assertSaltTrueReturn(ret)
        self.assertInSaltComment(expected_comment, ret)

    @pytest.mark.slow_test
    def test_local_archive_extracted_trim_output(self):
        """
        test archive.extracted with local file and trim_output set to 1
        """
        expected_changes = {
            "directories_created": ["/tmp/archive/"],
            "extracted_files": ["custom"],
        }
        ret = self.run_state(
            "archive.extracted",
            name=ARCHIVE_DIR,
            source=self.archive_local_tar_source,
            archive_format="tar",
            skip_files_list_verify=True,
            source_hash_update=True,
            source_hash=ARCHIVE_TAR_SHA_HASH,
            trim_output=1,
        )

        self.assertSaltTrueReturn(ret)
        self._check_extracted(self.untar_file)
        state_ret = ret["archive_|-/tmp/archive_|-/tmp/archive_|-extracted"]
        self.assertTrue(
            state_ret["comment"].endswith("Output was trimmed to 1 number of lines")
        )
        self.assertEqual(state_ret["changes"], expected_changes)

    @pytest.mark.slow_test
    def test_archive_compressed_zip_basic(self):
        """
        Test basic zip archive creation with archive.compressed
        """
        archive_path = os.path.join(ARCHIVE_DIR, "test.zip")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        # Create source file
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("test content")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
            archive_format="zip",
        )
        
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(archive_path))
        state_ret = list(ret.values())[0]
        self.assertIn("created", state_ret["changes"])
        self.assertEqual(state_ret["changes"]["created"], archive_path)

    @pytest.mark.slow_test
    def test_archive_compressed_tar_gz(self):
        """
        Test tar.gz archive creation with archive.compressed
        """
        archive_path = os.path.join(ARCHIVE_DIR, "test.tar.gz")
        source_dir = os.path.join(ARCHIVE_DIR, "source_dir")
        
        # Create source directory with files
        os.makedirs(source_dir, exist_ok=True)
        with salt.utils.files.fopen(os.path.join(source_dir, "file1.txt"), "w") as f:
            f.write("content 1")
        with salt.utils.files.fopen(os.path.join(source_dir, "file2.txt"), "w") as f:
            f.write("content 2")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_dir],
            archive_format="tar.gz",
        )
        
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(archive_path))
        state_ret = list(ret.values())[0]
        self.assertIn("Successfully created", state_ret["comment"])

    @pytest.mark.slow_test
    def test_archive_compressed_multiple_sources(self):
        """
        Test archive creation with multiple source files
        """
        archive_path = os.path.join(ARCHIVE_DIR, "multi.zip")
        source1 = os.path.join(ARCHIVE_DIR, "file1.txt")
        source2 = os.path.join(ARCHIVE_DIR, "file2.txt")
        
        # Create source files
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source1, "w") as f:
            f.write("content 1")
        with salt.utils.files.fopen(source2, "w") as f:
            f.write("content 2")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source1, source2],
        )
        
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(archive_path))
        state_ret = list(ret.values())[0]
        self.assertEqual(state_ret["changes"]["sources_added"], [source1, source2])

    @pytest.mark.slow_test
    def test_archive_compressed_already_exists(self):
        """
        Test that existing archive is not recreated by default
        """
        archive_path = os.path.join(ARCHIVE_DIR, "existing.zip")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        # Create source and archive
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("content")
        
        # First creation
        ret1 = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
        )
        self.assertSaltTrueReturn(ret1)
        
        # Second call without overwrite
        ret2 = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
        )
        self.assertSaltTrueReturn(ret2)
        state_ret = list(ret2.values())[0]
        self.assertIn("already exists", state_ret["comment"])
        self.assertEqual(state_ret["changes"], {})

    @pytest.mark.slow_test
    def test_archive_compressed_overwrite(self):
        """
        Test overwriting an existing archive
        """
        archive_path = os.path.join(ARCHIVE_DIR, "overwrite.zip")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        # Create source and archive
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("content")
        
        # First creation
        ret1 = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
        )
        self.assertSaltTrueReturn(ret1)
        
        # Second call with overwrite=True
        ret2 = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
            overwrite=True,
        )
        self.assertSaltTrueReturn(ret2)
        state_ret = list(ret2.values())[0]
        self.assertIn("created", state_ret["changes"])

    @pytest.mark.slow_test
    def test_archive_compressed_missing_source(self):
        """
        Test that missing sources are properly detected
        """
        archive_path = os.path.join(ARCHIVE_DIR, "test.zip")
        missing_source = os.path.join(ARCHIVE_DIR, "nonexistent.txt")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[missing_source],
        )
        
        self.assertSaltFalseReturn(ret)
        state_ret = list(ret.values())[0]
        self.assertIn("do not exist", state_ret["comment"])
        self.assertIn(missing_source, state_ret["comment"])

    @pytest.mark.slow_test
    def test_archive_compressed_test_mode(self):
        """
        Test archive.compressed in test mode
        """
        archive_path = os.path.join(ARCHIVE_DIR, "test.zip")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        # Create source file
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("content")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
            test=True,
        )
        
        state_ret = list(ret.values())[0]
        self.assertIsNone(state_ret["result"])
        self.assertIn("would be created", state_ret["comment"])
        self.assertFalse(os.path.isfile(archive_path))

    @pytest.mark.slow_test
    @pytest.mark.skipif(
        salt.utils.platform.is_windows(),
        reason="User/group ownership not applicable on Windows",
    )
    def test_archive_compressed_with_ownership(self):
        """
        Test archive creation with user/group ownership
        """
        archive_path = os.path.join(ARCHIVE_DIR, "owned.zip")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        # Create source file
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("content")
        
        # Get current user
        import pwd
        current_user = pwd.getpwuid(os.getuid()).pw_name
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
            user=current_user,
        )
        
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isfile(archive_path))
        # Verify file ownership
        stat_info = os.stat(archive_path)
        file_user = pwd.getpwuid(stat_info.st_uid).pw_name
        self.assertEqual(file_user, current_user)

    @pytest.mark.slow_test
    def test_archive_compressed_tar_formats(self):
        """
        Test different tar compression formats
        """
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("test content for compression")
        
        formats = ["tar", "tar.gz", "tar.bz2", "tar.xz"]
        
        for fmt in formats:
            archive_path = os.path.join(ARCHIVE_DIR, f"test.{fmt}")
            ret = self.run_state(
                "archive.compressed",
                name=archive_path,
                sources=[source_file],
                archive_format=fmt,
            )
            
            self.assertSaltTrueReturn(ret)
            self.assertTrue(os.path.isfile(archive_path), f"Archive {archive_path} was not created")

    @pytest.mark.slow_test
    def test_archive_compressed_invalid_format(self):
        """
        Test that unsupported archive formats are rejected
        """
        archive_path = os.path.join(ARCHIVE_DIR, "test.rar")
        source_file = os.path.join(ARCHIVE_DIR, "source.txt")
        
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        with salt.utils.files.fopen(source_file, "w") as f:
            f.write("content")
        
        ret = self.run_state(
            "archive.compressed",
            name=archive_path,
            sources=[source_file],
            archive_format="rar",
        )
        
        self.assertSaltFalseReturn(ret)
        state_ret = list(ret.values())[0]
        self.assertIn("Unsupported archive format", state_ret["comment"])


