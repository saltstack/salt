import os

import pytest
import yaml

# moto must be imported before boto3
try:
    import boto3
    from moto import mock_aws

    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

import salt.fileserver.s3fs as s3fs
import salt.utils.s3
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skipif(not HAS_BOTO, reason="Missing library moto or boto3"),
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def bucket():
    with mock_aws():
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
        "files/conf.d/foo.conf": {"content": "server {}"},
    }

    make_keys(bucket, s3, keys)
    s3fs.update()
    verify_cache(bucket, keys)

    # make a modification and update again - verify the change is retrieved
    keys["top.sls"]["content"] = yaml.dump({"base": {"*": ["foo", "bar"]}})
    make_keys(bucket, s3, keys)
    s3fs.update()
    verify_cache(bucket, keys)

    # verify that when files get deleted from s3, they also get deleted in
    # the local cache
    delete_file = "files/nginx.conf"
    del keys[delete_file]
    s3.delete_object(Bucket=bucket, Key=delete_file)

    s3fs.update()
    verify_cache(bucket, keys)

    cache_file = s3fs._get_cached_file_name(bucket, "base", delete_file)
    assert not os.path.exists(cache_file)

    # we want empty directories to get deleted from the local cache

    # after this one, `files` should still exist
    files_dir = os.path.dirname(cache_file)
    assert os.path.exists(files_dir)

    # but after the last file is deleted, the directory and any parents
    # should be deleted too
    delete_file = "files/conf.d/foo.conf"
    del keys[delete_file]
    s3.delete_object(Bucket=bucket, Key=delete_file)

    s3fs.update()
    verify_cache(bucket, keys)

    cache_file = s3fs._get_cached_file_name(bucket, "base", delete_file)
    assert not os.path.exists(cache_file)

    # after this, `files/conf.d` and `files` should be deleted
    conf_d_dir = os.path.dirname(cache_file)
    assert not os.path.exists(conf_d_dir)
    assert not os.path.exists(files_dir)


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
    cache_file = s3fs._get_buckets_cache_filename()
    s3fs._write_buckets_cache_file(metadata, cache_file)
    assert s3fs._read_buckets_cache_file(cache_file) == metadata


def test_ignore_pickle_load_exceptions():
    #  TODO: parameterized test with patched pickle.load that raises the
    #  various allowable exception from _read_buckets_cache_file
    pass


@pytest.mark.skip_on_fips_enabled_platform
def test_prune_deleted_files_multiple_envs_per_bucket(bucket, s3):
    """
    Test that _prune_deleted_files does not raise KeyError in
    multi-environment-per-bucket mode (issue #68335).

    Prior to the fix the function read meta["Key"] off the
    {bucket: [...]} dict it received as `meta`, raising
    KeyError: 'Key'. The fix descends one more level
    (meta.values() -> obj["Key"]) so the cached_files set is
    populated correctly.
    """

    # Create test files in S3 with the env as the first path component
    # (this is how multi-env-per-bucket mode discovers environments).
    keys = {
        "base/test1.sls": {"content": "test1 content"},
        "base/test2.sls": {"content": "test2 content"},
        "dev/test3.sls": {"content": "test3 content"},
    }
    make_keys(bucket, s3, keys)

    # Override s3.buckets to a list, which switches s3fs into
    # multi-env-per-bucket mode (vs. the dict form set by the fixture).
    with patch.dict(s3fs.__opts__, {"s3.buckets": [bucket]}):
        # Populate the cache so update() lays down real files.
        s3fs.update()

        # In multi-env mode the env prefix is part of the S3 key, so the
        # cached path is <cachedir>/<env>/<bucket>/<env>/<filename>.
        for key in keys:
            env = key.split("/", 1)[0]
            cache_file = s3fs._get_cached_file_name(bucket, env, key)
            assert os.path.exists(cache_file)

        # Hand-built metadata in the shape s3fs._init() produces for
        # multi-env-per-bucket mode: {saltenv: [{bucket_name: [file_meta]}]}.
        # Prior to the fix this exact structure caused KeyError: 'Key'.
        metadata = {
            "base": [
                {
                    bucket: [
                        {"Key": "base/test1.sls"},
                        {"Key": "base/test2.sls"},
                    ]
                }
            ],
            "dev": [{bucket: [{"Key": "dev/test3.sls"}]}],
        }

        # The fix is verified by this call returning without raising.
        s3fs._prune_deleted_files(metadata)


@pytest.mark.skip_on_fips_enabled_platform
def test_prune_deleted_files_single_env_per_bucket(bucket, s3):
    """Test that _prune_deleted_files works correctly with single environment per bucket."""

    # The configure_loader_modules fixture already sets s3.buckets to
    # {"base": [bucket]} (dict form = env-per-bucket mode).
    keys = {
        "test1.sls": {"content": "test1 content"},
        "test2.sls": {"content": "test2 content"},
    }
    make_keys(bucket, s3, keys)

    # Initial update to populate cache
    s3fs.update()

    # Verify files are cached
    for key in keys:
        cache_file = s3fs._get_cached_file_name(bucket, "base", key)
        assert os.path.exists(cache_file)

    # Delete one file from S3
    s3.delete_object(Bucket=bucket, Key="test1.sls")
    del keys["test1.sls"]

    # Metadata in the shape s3fs._init() produces for env-per-bucket mode.
    metadata = {"base": [{bucket: [{"Key": "test2.sls"}]}]}

    # Call _prune_deleted_files directly
    s3fs._prune_deleted_files(metadata)

    # Verify that deleted file was removed from cache
    deleted_cache_file = s3fs._get_cached_file_name(bucket, "base", "test1.sls")
    assert not os.path.exists(deleted_cache_file)

    # Verify that remaining file still exists
    remaining_cache_file = s3fs._get_cached_file_name(bucket, "base", "test2.sls")
    assert os.path.exists(remaining_cache_file)
