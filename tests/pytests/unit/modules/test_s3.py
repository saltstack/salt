"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.s3
"""

import pytest

import salt.modules.s3 as s3
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {s3: {"__utils__": {"s3.query": MagicMock(return_value="A")}}}


def test__get_key_defaults():
    mock = MagicMock(return_value="")
    with patch.dict(s3.__salt__, {"config.option": mock}):
        (
            key,
            keyid,
            service_url,
            verify_ssl,
            kms_keyid,
            location,
            role_arn,
            path_style,
            https_enable,
        ) = s3._get_key(None, None, None, None, None, None, None, None, None)
        assert None is role_arn
        assert None is key
        assert None is keyid
        assert "s3.amazonaws.com" == service_url
        assert "" == verify_ssl
        assert "" == location
        assert "" == path_style
        assert "" == https_enable


def test_delete():
    """
    Test for delete a bucket, or delete an object from a bucket.
    """
    with patch.object(
        s3,
        "_get_key",
        return_value=(
            "key",
            "keyid",
            "service_url",
            "verify_ssl",
            "kms_keyid",
            "location",
            "role_arn",
            "path_style",
            "https_enable",
        ),
    ):
        assert s3.delete("bucket") == "A"


def test_get():
    """
    Test for list the contents of a bucket, or return an object from a
    bucket.
    """
    with patch.object(
        s3,
        "_get_key",
        return_value=(
            "key",
            "keyid",
            "service_url",
            "verify_ssl",
            "kms_keyid",
            "location",
            "role_arn",
            "path_style",
            "https_enable",
        ),
    ):
        assert s3.get() == "A"


def test_head():
    """
    Test for return the metadata for a bucket, or an object in a bucket.
    """
    with patch.object(
        s3,
        "_get_key",
        return_value=(
            "key",
            "keyid",
            "service_url",
            "verify_ssl",
            "kms_keyid",
            "location",
            "role_arn",
            "path_style",
            "https_enable",
        ),
    ):
        assert s3.head("bucket") == "A"


def test_put():
    """
    Test for create a new bucket, or upload an object to a bucket.
    """
    with patch.object(
        s3,
        "_get_key",
        return_value=(
            "key",
            "keyid",
            "service_url",
            "verify_ssl",
            "kms_keyid",
            "location",
            "role_arn",
            "path_style",
            "https_enable",
        ),
    ):
        assert s3.put("bucket") == "A"
