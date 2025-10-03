"""
    Unit test for salt.grains.metadata


    :codeauthor: :email" `Gareth J. Greenaway <ggreenaway@vmware.com>

"""

import logging

import pytest

import salt.grains.metadata as metadata
import salt.utils.http as http
from tests.support.mock import MagicMock, create_autospec, patch

log = logging.getLogger(__name__)


class MockSocketClass:
    def __init__(self, *args, **kwargs):
        pass

    def settimeout(self, *args, **kwargs):
        pass

    def connect_ex(self, *args, **kwargs):
        return 0


@pytest.fixture
def configure_loader_modules():
    return {metadata: {"__opts__": {"metadata_server_grains": "True"}}}


def test_metadata_search():
    def mock_http(
        url="",
        method="GET",
        headers=False,
        header_list=None,
        header_dict=None,
        status=False,
    ):
        metadata_vals = {
            "http://169.254.169.254/latest/api/token": {
                "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
                "status": 200,
                "headers": {},
            },
            "http://169.254.169.254/latest/": {
                "body": "meta-data",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/": {
                "body": "ami-id\nami-launch-index\nami-manifest-path\nhostname",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-id": {
                "body": "ami-xxxxxxxxxxxxxxxxx",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-launch-index": {
                "body": "0",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/ami-manifest-path": {
                "body": "(unknown)",
                "headers": {},
            },
            "http://169.254.169.254/latest/meta-data/hostname": {
                "body": "ip-xx-x-xx-xx.us-west-2.compute.internal",
                "headers": {},
            },
        }

        return metadata_vals[url]

    with patch(
        "salt.utils.http.query",
        create_autospec(http.query, autospec=True, side_effect=mock_http),
    ):
        ret = metadata.metadata()
        assert ret == {
            "meta-data": {
                "ami-id": "ami-xxxxxxxxxxxxxxxxx",
                "ami-launch-index": "0",
                "ami-manifest-path": "(unknown)",
                "hostname": "ip-xx-x-xx-xx.us-west-2.compute.internal",
            }
        }

    with patch.dict(
        metadata.__context__,
        {
            "metadata_aws_token": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=="
        },
    ):
        with patch(
            "salt.utils.http.query",
            create_autospec(http.query, autospec=True, side_effect=mock_http),
        ):
            ret = metadata.metadata()
            assert ret == {
                "meta-data": {
                    "ami-id": "ami-xxxxxxxxxxxxxxxxx",
                    "ami-launch-index": "0",
                    "ami-manifest-path": "(unknown)",
                    "hostname": "ip-xx-x-xx-xx.us-west-2.compute.internal",
                }
            }


def test_metadata_refresh_token():
    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query,
            autospec=True,
            return_value={
                "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
            },
        ),
    ):
        metadata._refresh_token()
        assert "metadata_aws_token" in metadata.__context__
        assert (
            metadata.__context__["metadata_aws_token"]
            == "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX=="
        )


def test_metadata_virtual():
    with patch("socket.socket", MagicMock(return_value=MockSocketClass())):
        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                return_value={"error": "[Errno -2] Name or service not known"},
            ),
        ):
            assert metadata.__virtual__() is False

        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                return_value={
                    "body": "dynamic\nmeta-data\nuser-data",
                    "status": 200,
                },
            ),
        ):
            assert metadata.__virtual__() is True

        with patch(
            "salt.utils.http.query",
            create_autospec(
                http.query,
                autospec=True,
                side_effect=[
                    {
                        "body": "",
                        "status": 401,
                    },
                    {
                        "body": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX==",
                    },
                    {
                        "body": "dynamic\nmeta-data\nuser-data",
                        "status": 200,
                    },
                ],
            ),
        ):
            assert metadata.__virtual__() is True
