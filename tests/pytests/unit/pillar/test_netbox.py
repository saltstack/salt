import logging

import pytest
import salt.pillar.netbox as netbox_pillar
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import Mock, patch
from tests.support.unit import TestCase


class NetboxPillarTestCase(TestCase, LoaderModuleMockMixin):
    @pytest.mark.parametrize(
        "api_url,app,endpoint,api_token",
        [
            ("http://netbox.example.com/api", "dcim", "devices", "t0ken123"),
            (
                "http://netbox.example.com/api",
                "virtualization",
                "devices",
                "virtual-machines",
            ),
        ],
    )
    def test_mock_url(api_url, app, endpoint, api_token):
        http_body = {
            "count": 0,
            "next": "{}/{}/{}/?limit=50&offset=50".format(api_url, app, endpoint),
            "previous": null,
            "results": [],
        }

        query_ret = {"body": http_body, "status": 200}
        with patch("salt.utils.http.query", return_value=query_ret) as http_mock:
            task = netbox_pillar.ext_pillar(
                mid="minion1",
                pillar=None,
                api_url=api_url,
                api_token=api_token,
                endpoint=endpoint,
            )
        http_mock.assert_called_once_with(
            "{}/{}/{}".format(api_url, app, endpoint), status=True,
        )
        self.assertEqual(0, task["count"])
