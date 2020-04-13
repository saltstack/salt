# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.modules.glance as glance
import salt.modules.salt_version
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase


class GlanceTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {
            glance: {
                "__salt__": {
                    "salt_version.less_than": salt.modules.salt_version.less_than
                }
            },
        }

    def test_image_list(self):
        """
        test salt.modles.glance
        """
        name = "test"
        image = MagicMock()
        image.name = name
        attrs = {
            "images.list.return_value": [image],
        }
        mock_auth = MagicMock(**attrs)
        patch_auth = patch("salt.modules.glance._auth", return_value=mock_auth)

        with patch_auth:
            ret = glance.image_list(id="test_id", name=name)
            assert ret[0]["name"] == name
