# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.pecl as pecl

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PeclTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.pecl
    """

    def setup_loader_modules(self):
        return {pecl: {}}

    # 'installed' function tests: 1

    def test_installed(self):
        """
        Test to make sure that a pecl extension is installed.
        """
        name = "mongo"
        ver = "1.0.1"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock_lst = MagicMock(return_value={name: "stable"})
        mock_t = MagicMock(return_value=True)
        with patch.dict(pecl.__salt__, {"pecl.list": mock_lst, "pecl.install": mock_t}):
            comt = "Pecl extension {0} is already installed.".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(pecl.installed(name), ret)

            with patch.dict(pecl.__opts__, {"test": True}):
                comt = "Pecl extension mongo-1.0.1 would have been installed"
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(pecl.installed(name, version=ver), ret)

            with patch.dict(pecl.__opts__, {"test": False}):
                comt = "Pecl extension mongo-1.0.1 was successfully installed"
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {"mongo-1.0.1": "Installed"},
                    }
                )
                self.assertDictEqual(pecl.installed(name, version=ver), ret)

    # 'removed' function tests: 1

    def test_removed(self):
        """
        Test to make sure that a pecl extension is not installed.
        """
        name = "mongo"

        ret = {"name": name, "result": None, "comment": "", "changes": {}}

        mock_lst = MagicMock(side_effect=[{}, {name: "stable"}, {name: "stable"}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(
            pecl.__salt__, {"pecl.list": mock_lst, "pecl.uninstall": mock_t}
        ):
            comt = "Pecl extension {0} is not installed.".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(pecl.removed(name), ret)

            with patch.dict(pecl.__opts__, {"test": True}):
                comt = "Pecl extension mongo would have been removed"
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(pecl.removed(name), ret)

            with patch.dict(pecl.__opts__, {"test": False}):
                comt = "Pecl extension mongo was successfully removed."
                ret.update(
                    {"comment": comt, "result": True, "changes": {name: "Removed"}}
                )
                self.assertDictEqual(pecl.removed(name), ret)
