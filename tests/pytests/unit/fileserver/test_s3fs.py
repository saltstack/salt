import os

import boto3
import pytest
import yaml

# moto must be imported before boto3
from moto import mock_s3

import salt.fileserver.s3fs as s3fs
import salt.utils.s3


@pytest.fixture
def bucket():
    with mock_s3():
        yield "mybucket"


@pytest.fixture(scope="module")
def aws_creds():
    return {
        "aws_access_key_id": "testing",
        "aws_secret_access_key": "testing",
        "aws_session_token": "testing",
        "region_name": "us-east-1",
    }


@pytest.fixture(scope="function")
def configure_loader_modules(tmp_path, bucket):
    opts = {
        "cachedir": tmp_path,
        "s3.buckets": {"base": [bucket]},
        "s3.location": "us-east-1",
        "s3.s3_cache_expire": -1,
    }
    utils = {"s3.query": salt.utils.s3.query}

    yield {s3fs: {"__opts__": opts, "__utils__": utils}}


@pytest.fixture(scope="function")
def s3(bucket, aws_creds):
    conn = boto3.client("s3", **aws_creds)
    conn.create_bucket(Bucket=bucket)
    return conn


def make_keys(bucket, conn, keys):
    for key, data in keys.items():
        conn.put_object(
            Bucket=bucket,
            Key=key,
            Body=data["content"],
        )


def verify_cache(bucket, expected):
    for key, data in expected.items():
        correct_content = data["content"]
        cache_file = s3fs._get_cached_file_name(bucket, "base", key)
        assert os.path.exists(cache_file)

        if correct_content is None:
            continue

        with salt.utils.files.fopen(cache_file) as f:
            content = f.read()
            assert correct_content == content


@pytest.mark.skip_on_fips_enabled_platform
def test_update(bucket, s3):
    """Tests that files get downloaded from s3 to the local cache."""

    keys = {
        "top.sls": {"content": yaml.dump({"base": {"*": ["foo"]}})},
        "foo.sls": {"content": yaml.dump({"nginx": {"pkg.installed": []}})},
        "files/nginx.conf": {"content": "server {}"},
    }

    make_keys(bucket, s3, keys)
    s3fs.update()
    verify_cache(bucket, keys)

    # make a modification and update again - verify the change is retrieved
    keys["top.sls"]["content"] = yaml.dump({"base": {"*": ["foo", "bar"]}})
    make_keys(bucket, s3, keys)
    s3fs.update()
    verify_cache(bucket, keys)


@pytest.mark.skip_on_fips_enabled_platform
def test_s3_hash(bucket, s3):
    """Verifies that s3fs hashes files correctly."""

    keys = {
        "top.sls": {"content": yaml.dump({"base": {"*": ["foo"]}})},
        "foo.sls": {"content": yaml.dump({"nginx": {"pkg.installed": []}})},
        "files/nginx.conf": {"content": "server {}"},
    }

    make_keys(bucket, s3, keys)
    s3fs.update()

    for key, item in keys.items():
        cached_file_path = s3fs._get_cached_file_name(bucket, "base", key)
        item["hash"] = salt.utils.hashutils.get_hash(
            cached_file_path, s3fs.S3_HASH_TYPE
        )
        item["cached_file_path"] = cached_file_path

    load = {"saltenv": "base"}
    fnd = {"bucket": bucket}

    for key, item in keys.items():
        fnd["path"] = item["cached_file_path"]
        actual_hash = s3fs.file_hash(load, fnd)
        assert s3fs.S3_HASH_TYPE == actual_hash["hash_type"]
        assert item["hash"] == actual_hash["hsum"]


@pytest.mark.skip_on_fips_enabled_platform
def test_cache_round_trip(bucket):
    metadata = {"foo": "bar"}
    cache_file = s3fs._get_cached_file_name(bucket, "base", "somefile")

    s3fs._write_buckets_cache_file(metadata, cache_file)
    assert s3fs._read_buckets_cache_file(cache_file) == metadata


def test_ignore_pickle_load_exceptions():
    #  TODO: parameterized test with patched pickle.load that raises the
    #  various allowable exception from _read_buckets_cache_file
    pass
