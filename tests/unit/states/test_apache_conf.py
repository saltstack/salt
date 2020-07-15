# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.apache_conf as apache_conf

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ApacheConfTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.apache_conf
    """

    def setup_loader_modules(self):
        return {apache_conf: {}}

    # 'enabled' function tests: 1

    def test_enabled(self):
        """
        Test to ensure an Apache conf is enabled.
        """
        name = "saltstack.com"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, False, False])
        mock_str = MagicMock(return_value={"Status": ["enabled"]})
        with patch.dict(
            apache_conf.__salt__,
            {"apache.check_conf_enabled": mock, "apache.a2enconf": mock_str},
        ):
            comt = "{0} already enabled.".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(apache_conf.enabled(name), ret)

            comt = "Apache conf {0} is set to be enabled.".format(name)
            ret.update(
                {"comment": comt, "result": None, "changes": {"new": name, "old": None}}
            )
            with patch.dict(apache_conf.__opts__, {"test": True}):
                self.assertDictEqual(apache_conf.enabled(name), ret)

            comt = "Failed to enable {0} Apache conf".format(name)
            ret.update({"comment": comt, "result": False, "changes": {}})
            with patch.dict(apache_conf.__opts__, {"test": False}):
                self.assertDictEqual(apache_conf.enabled(name), ret)

    # 'disabled' function tests: 1

    def test_disabled(self):
        """
        Test to ensure an Apache conf is disabled.
        """
        name = "saltstack.com"

        ret = {"name": name, "result": None, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, True, False])
        mock_str = MagicMock(return_value={"Status": ["disabled"]})
        with patch.dict(
            apache_conf.__salt__,
            {"apache.check_conf_enabled": mock, "apache.a2disconf": mock_str},
        ):
            comt = "Apache conf {0} is set to be disabled.".format(name)
            ret.update({"comment": comt, "changes": {"new": None, "old": name}})
            with patch.dict(apache_conf.__opts__, {"test": True}):
                self.assertDictEqual(apache_conf.disabled(name), ret)

            comt = "Failed to disable {0} Apache conf".format(name)
            ret.update({"comment": comt, "result": False, "changes": {}})
            with patch.dict(apache_conf.__opts__, {"test": False}):
                self.assertDictEqual(apache_conf.disabled(name), ret)

            comt = "{0} already disabled.".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(apache_conf.disabled(name), ret)
