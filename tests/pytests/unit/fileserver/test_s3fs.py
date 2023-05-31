import pytest

import salt.fileserver.s3fs as s3fs


@pytest.fixture
def configure_loader_modules(tmp_path):
    opts = {
        "cachedir": tmp_path,
    }
    return {s3fs: {"__opts__": opts}}


def test_cache_round_trip():
    metadata = {"foo": "bar"}
    cache_file = s3fs._get_cached_file_name("base", "fake_bucket", "some_file")

    s3fs._write_buckets_cache_file(metadata, cache_file)
    assert s3fs._read_buckets_cache_file(cache_file) == metadata


def test_ignore_pickle_load_exceptions():
    #  TODO: parameterized test with patched pickle.load that raises the
    #  various allowable exception from _read_buckets_cache_file
    pass
