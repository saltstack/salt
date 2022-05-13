import logging

import salt.pillar.s3 as s3_pillar
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class S3PillarTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.pillar.s3
    """

    def setup_loader_modules(self):
        s3_pillar_globals = {"__utils__": {}}
        return {s3_pillar: s3_pillar_globals}

    def test_refresh_buckets_cache_file(self):
        """
        Test pagination with refresh_buckets_cache_file
        """
        key = "XXXXXXXXXXXXXXXXXXXXX"
        keyid = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        bucket = "dummy_bucket"
        service_url = "s3.amazonaws.com"
        cache_file = "dummy_file"

        s3_creds = s3_pillar.S3Credentials(key, keyid, bucket, service_url)

        mock_return_first = [
            {"Name": "pillar-bucket"},
            {"Prefix": "test"},
            {"KeyCount": "10"},
            {"MaxKeys": "10"},
            {"NextContinuationToken": "XXXXX"},
            {"IsTruncated": "true"},
        ]

        mock_return_second = [
            {"Name": "pillar-bucket"},
            {"Prefix": "test"},
            {"KeyCount": "10"},
            {"MaxKeys": "10"},
            {"IsTruncated": "true"},
        ]

        first_range_end = 999
        second_range_end = 1200
        for i in range(0, first_range_end):
            key_name = "{}/init.sls".format(i)
            tmp = {
                "Key": key_name,
                "LastModified": "2019-12-18T15:54:39.000Z",
                "ETag": '"fba0a053704e8b357c94be90b44bb640"',
                "Size": "5 ",
                "StorageClass": "STANDARD",
            }
            mock_return_first.append(tmp)

        for i in range(first_range_end, second_range_end):
            key_name = "{}/init.sls".format(i)
            tmp = {
                "Key": key_name,
                "LastModified": "2019-12-18T15:54:39.000Z",
                "ETag": '"fba0a053704e8b357c94be90b44bb640"',
                "Size": "5 ",
                "StorageClass": "STANDARD",
            }
            mock_return_second.append(tmp)

        _expected = {"base": {"dummy_bucket": []}}
        for i in range(0, second_range_end):
            key_name = "{}/init.sls".format(i)
            tmp = {
                "Key": key_name,
                "LastModified": "2019-12-18T15:54:39.000Z",
                "ETag": '"fba0a053704e8b357c94be90b44bb640"',
                "Size": "5 ",
                "StorageClass": "STANDARD",
            }
            _expected["base"]["dummy_bucket"].append(tmp)

        mock_s3_query = MagicMock(side_effect=[mock_return_first, mock_return_second])
        with patch.dict(s3_pillar.__utils__, {"s3.query": mock_s3_query}):
            with patch("salt.utils.files.fopen", mock_open(read_data=b"")):
                ret = s3_pillar._refresh_buckets_cache_file(
                    s3_creds, cache_file, False, "base", ""
                )
                self.assertEqual(ret, _expected)
