import tempfile

import salt.fileserver.s3fs as s3fs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class S3fsFileTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        opts = {
            "cachedir": self.tmp_cachedir,
        }
        return {s3fs: {"__opts__": opts}}

    @classmethod
    def setUpClass(cls):
        cls.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    def test_cache_round_trip(self):
        metadata = {"foo": "bar"}
        cache_file = s3fs._get_cached_file_name("base", "fake_bucket", "some_file")

        s3fs._write_buckets_cache_file(metadata, cache_file)
        assert s3fs._read_buckets_cache_file(cache_file) == metadata

    def test_ignore_pickle_load_exceptions(self):
        #  TODO: parameterized test with patched pickle.load that raises the
        #  various allowable exception from _read_buckets_cache_file
        pass
