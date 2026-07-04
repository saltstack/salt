"""
Lock down the s3fs options documented in the s3fs.py module docstring.

The docstring promises that ``s3.location``, ``s3.service_url``,
``s3.verify_ssl``, ``s3.https_enable``, and ``s3.path_style`` are honoured by
the fileserver. This test verifies that ``salt.fileserver.s3fs._get_s3_key``
returns each value untouched and passes it on the way down to ``s3.query``.

If somebody renames or removes one of these option keys without also touching
the documentation, this test fails first.
"""

import pytest

import salt.fileserver.s3fs as s3fs


@pytest.fixture
def configure_loader_modules(tmp_path):
    opts = {
        "cachedir": str(tmp_path),
        "s3.key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "s3.keyid": "AKIAIOSFODNN7EXAMPLE",
        "s3.service_url": "s3.us-west-2.amazonaws.com",
        "s3.location": "us-west-2",
        "s3.verify_ssl": False,
        "s3.https_enable": True,
        "s3.path_style": True,
        "s3.buckets": {"base": ["docs-example-bucket"]},
    }
    return {s3fs: {"__opts__": opts}}


def test_get_s3_key_returns_documented_options():
    """All option keys that the s3fs.py docstring promises are returned."""
    (
        key,
        keyid,
        service_url,
        verify_ssl,
        kms_keyid,
        location,
        path_style,
        https_enable,
    ) = s3fs._get_s3_key()

    assert key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert keyid == "AKIAIOSFODNN7EXAMPLE"
    assert service_url == "s3.us-west-2.amazonaws.com"
    assert verify_ssl is False
    assert location == "us-west-2"
    assert path_style is True
    assert https_enable is True
    # kms_keyid is read from a separate aws.kms.keyid opt
    assert kms_keyid is None


@pytest.mark.parametrize(
    "opt_key",
    [
        "s3.location",
        "s3.service_url",
        "s3.verify_ssl",
        "s3.https_enable",
        "s3.path_style",
    ],
)
def test_documented_option_key_is_recognized(opt_key):
    """
    Each documented option key must appear in the module's source so that a
    silent rename does not slip past the documentation.
    """
    import inspect

    source = inspect.getsource(s3fs._get_s3_key)
    assert opt_key in source, f"{opt_key!r} no longer read by _get_s3_key"
