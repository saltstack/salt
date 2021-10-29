"""
    Unit test for salt.grains.metadata_gce


    :codeauthor: :email" `Thomas Phipps <tphipps@vmware.com>

"""

import logging
#import pytest

try:
    import salt.grains.metadata_gce as metadata
    from tests.support.mock import MagicMock, patch
except ImportError:
    pass

log = logging.getLogger(__name__)

metadata_vals = {
        'http://169.254.169.254/computeMetadata/v1/': {
            "body": "instance/",
            "headers": {"Content-Type": "application/octet-stream", "Metadata-Flavor": "Google"}
            },
        'http://169.254.169.254/computeMetadata/v1/instance/': {
            "body": "test",
            "headers": {"Content-Type": "application/octet-stream", "Metadata-Flavor": "Google"}
            },
        'http://169.254.169.254/computeMetadata/v1/instance/test': {
            "body": "fulltest",
            "headers": {"Content-Type": "application/octet-stream", "Metadata-Flavor": "Google"}
            }
        }


def mock_http(url="", headers=False, header_list=None):
    print(url)
    return metadata_vals[url]


def test_metadata_gce_search():
    with patch("salt.utils.http.query", MagicMock(side_effect=[mock_http, mock_http, mock_http])) as testing:
        assert metadata._search() == "instance/"
