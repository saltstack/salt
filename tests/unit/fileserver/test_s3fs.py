import errno
import logging
import pickle
import tempfile

import salt.fileserver.s3fs as s3fs
import salt.utils.files
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class S3fsFileTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        opts = {
            "cachedir": self.tmp_cachedir,
        }
        return {s3fs: {"__opts__": opts}}

    @classmethod
    def setUpClass(cls):
        cls.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        try:
            salt.utils.files.rm_rf(cls.tmp_cachedir)
        except OSError as exc:
            if exc.errno == errno.EACCES:
                log.error("Access error removing file %s", cls.tmp_cachedir)
            elif exc.errno != errno.EEXIST:
                raise

    def setUp(self):
        self.cache_file = s3fs._get_cached_file_name("fake_bucket", "base", "some_file")
        s3fs._write_buckets_cache_file(dict(), self.cache_file)

    def tearDown(self):
        try:
            salt.utils.files.rm_rf(self.cache_file)
        except OSError as exc:
            if exc.errno == errno.EACCES:
                log.error("Access error removing file %s", self.cache_file)
            elif exc.errno != errno.EEXIST:
                raise

    def test_cache_round_trip(self):
        metadata = {"foo": "bar"}
        s3fs._write_buckets_cache_file(metadata, self.cache_file)
        self.assertDictEqual(s3fs._read_buckets_cache_file(self.cache_file), metadata)

    def test_ignore_pickle_load_exceptions(self):
        """
        Confirm that None is returned for desired exceptions when unpickling cache.
        """
        with patch("pickle.load") as load:
            exc_classes = [
                pickle.UnpicklingError,
                AttributeError,
                EOFError,
                ImportError,
                IndexError,
                KeyError,
                ValueError,
            ]
            for exc_class in exc_classes:
                with self.subTest(exc_class=exc_class):
                    load.side_effect = exc_class
                    self.assertIs(s3fs._read_buckets_cache_file(self.cache_file), None)
