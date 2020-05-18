# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy

# Import Salt Libs
import salt.utils.json
from salt.cloud.clouds import scaleway

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DummyRequest(object):
    def __init__(self, status_code, **response):
        self.status_code = status_code
        self.response = response

    def __getitem__(self, item):
        if item == "status":
            return self.status_code
        elif item in self.response:
            return self.response[item]
        raise KeyError(item)


class ScalewayTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.cloud.clouds.scaleway
    """

    _profile = {
        "profile": "my_scaleway",
        "name": "foo",
        "driver": "scaleway",
        "token": "foobarbaz",
    }

    def setup_loader_modules(self):
        return {
            scaleway: {
                "__utils__": {},
                "__opts__": {
                    "providers": {"my_scaleway": {}},
                    "profiles": {"my_scaleway": {}},
                },
            }
        }

    def test_query(self):
        """
        Confirm that using a different root affects the HTTP query made
        """
        body = '{"result": "success"}'
        server_id = "foo"
        expected = salt.utils.json.loads(body)
        http_query = MagicMock(return_value=DummyRequest(200, body=body))
        utils_dunder = {"http.query": http_query}

        with patch.dict(scaleway.__utils__, utils_dunder):

            # Case 1: use default api_root
            profile = copy.copy(self._profile)
            with patch.object(scaleway, "get_configured_provider", lambda: profile):
                result = scaleway.query(server_id=server_id)
                assert result == expected, result
                http_query.assert_called_once_with(
                    "https://cp-par1.scaleway.com/servers/foo/",
                    data="{}",
                    headers={
                        "X-Auth-Token": "foobarbaz",
                        "User-Agent": "salt-cloud",
                        "Content-Type": "application/json",
                    },
                    method="GET",
                )

            # Case 2: api_root overridden in profile
            http_query.reset_mock()
            profile = copy.copy(self._profile)
            profile["api_root"] = "https://my.api.root"
            with patch.object(scaleway, "get_configured_provider", lambda: profile):
                result = scaleway.query(server_id=server_id)
                assert result == expected, result
                http_query.assert_called_once_with(
                    "https://my.api.root/servers/foo/",
                    data="{}",
                    headers={
                        "X-Auth-Token": "foobarbaz",
                        "User-Agent": "salt-cloud",
                        "Content-Type": "application/json",
                    },
                    method="GET",
                )

            # Case 3: use default alternative root
            http_query.reset_mock()
            profile = copy.copy(self._profile)
            with patch.object(scaleway, "get_configured_provider", lambda: profile):
                result = scaleway.query(server_id=server_id, root="alt_root")
                assert result == expected, result
                http_query.assert_called_once_with(
                    "https://api-marketplace.scaleway.com/servers/foo/",
                    data="{}",
                    headers={
                        "X-Auth-Token": "foobarbaz",
                        "User-Agent": "salt-cloud",
                        "Content-Type": "application/json",
                    },
                    method="GET",
                )

            # Case 4: use alternative root specified in profile
            http_query.reset_mock()
            profile = copy.copy(self._profile)
            profile["alt_root"] = "https://my.alt.api.root"
            with patch.object(scaleway, "get_configured_provider", lambda: profile):
                result = scaleway.query(server_id=server_id, root="alt_root")
                assert result == expected, result
                http_query.assert_called_once_with(
                    "https://my.alt.api.root/servers/foo/",
                    data="{}",
                    headers={
                        "X-Auth-Token": "foobarbaz",
                        "User-Agent": "salt-cloud",
                        "Content-Type": "application/json",
                    },
                    method="GET",
                )
