# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.apache as apache
import salt.utils.files

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class ApacheTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.apache
    """

    def setup_loader_modules(self):
        return {apache: {}}

    # 'configfile' function tests: 1

    def test_configfile(self):
        """
        Test to allows for inputting a yaml dictionary into a file
        for apache configuration files.
        """
        with patch("os.path.exists", MagicMock(return_value=True)):
            name = "/etc/distro/specific/apache.conf"
            config = 'VirtualHost: this: "*:80"'
            new_config = 'LiteralHost: that: "*:79"'

            ret = {"name": name, "result": True, "changes": {}, "comment": ""}

            with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
                mock_config = MagicMock(return_value=config)
                with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                    ret.update({"comment": "Configuration is up to date."})
                    self.assertDictEqual(apache.configfile(name, config), ret)

            with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
                mock_config = MagicMock(return_value=new_config)
                with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                    ret.update(
                        {
                            "comment": "Configuration will update.",
                            "changes": {"new": new_config, "old": config},
                            "result": None,
                        }
                    )
                    with patch.dict(apache.__opts__, {"test": True}):
                        self.assertDictEqual(apache.configfile(name, new_config), ret)

            with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
                mock_config = MagicMock(return_value=new_config)
                with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                    ret.update(
                        {
                            "comment": "Successfully created configuration.",
                            "result": True,
                        }
                    )
                    with patch.dict(apache.__opts__, {"test": False}):
                        self.assertDictEqual(apache.configfile(name, config), ret)
