"""
    Unit test for salt.grains.metadata_azure


    :codeauthor: :email" `Vishal Gupta <guvishal@vmware.com>

"""

import logging

import pytest

import salt.grains.metadata_azure as metadata
import salt.utils.http as http
from tests.support.mock import create_autospec, patch

# from Exception import Exception, ValueError

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {metadata: {"__opts__": {"metadata_server_grains": "True"}}}


def test_metadata_azure_search():
    def mock_http(url="", headers=False, header_list=None):
        metadata_vals = {
            "http://169.254.169.254/metadata/instance?api-version=2020-09-01": {
                "body": '{"compute": {"test": "fulltest"}}',
                "headers": {"Content-Type": "application/json; charset=utf-8"},
            },
        }

        return metadata_vals[url]

    with patch(
        "salt.utils.http.query",
        create_autospec(http.query, autospec=True, side_effect=mock_http),
    ):
        assert metadata.metadata() == {"compute": {"test": "fulltest"}}


def test_metadata_virtual():
    print("running 1st")
    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query,
            autospec=True,
            return_value={
                "error": "Bad request: . Required metadata header not specified"
            },
        ),
    ):
        assert metadata.__virtual__() is False
    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query,
            autospec=True,
            return_value={
                "body": '{"compute": {"test": "fulltest"}}',
                "headers": {"Content-Type": "application/json; charset=utf-8"},
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
            return_value={
                "body": "test",
                "headers": {"Content-Type": "application/json; charset=utf-8"},
                "status": 404,
            },
        ),
    ):
        assert metadata.__virtual__() is False
    with patch(
        "salt.utils.http.query",
        create_autospec(
            http.query,
            autospec=True,
            return_value={
                "body": "test",
                "headers": {"Content-Type": "application/json; charset=utf-8"},
                "status": 400,
            },
        ),
    ):
        assert metadata.__virtual__() is False
