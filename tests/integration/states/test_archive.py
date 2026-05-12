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
