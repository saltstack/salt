"""
tests.unit.modules.test_glassfish
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the glassfish module
"""
import logging

import salt.modules.glassfish as glassfish
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class GlassFishTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {glassfish: {}}

    def test__api_get(self):
        get_mock = MagicMock()
        with patch("salt.modules.glassfish.requests.get", get_mock):
            glassfish._api_get("ThePath", server=glassfish.DEFAULT_SERVER)

        get_mock.assert_called_once_with(
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-By": "GlassFish REST HTML interface",
            },
            url="http://localhost:4848/management/domain/ThePath",
            verify=True,
            auth=None,
        )

    def test__api_post(self):
        post_mock = MagicMock()
        with patch("salt.modules.glassfish.requests.post", post_mock):
            glassfish._api_post("ThePath", {1: 1}, server=glassfish.DEFAULT_SERVER)

        post_mock.assert_called_once_with(
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-By": "GlassFish REST HTML interface",
            },
            url="http://localhost:4848/management/domain/ThePath",
            verify=True,
            auth=None,
            data='{"1": 1}',
        )

    def test__api_delete(self):
        delete_mock = MagicMock()
        with patch("salt.modules.glassfish.requests.delete", delete_mock):
            glassfish._api_delete("ThePath", {1: 1}, server=glassfish.DEFAULT_SERVER)

        delete_mock.assert_called_once_with(
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-By": "GlassFish REST HTML interface",
            },
            url="http://localhost:4848/management/domain/ThePath",
            verify=True,
            auth=None,
            params={1: 1},
        )
