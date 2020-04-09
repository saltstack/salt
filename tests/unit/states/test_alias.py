# -*- coding: utf-8 -*-
"""
unit tests for the alias state
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.alias as alias

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class AliasTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the alias state
    """

    def setup_loader_modules(self):
        return {alias: {}}

    def test_present_has_target(self):
        """
        test alias.present has target already
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Alias {0} already present".format(name),
            "changes": {},
            "name": name,
            "result": True,
        }

        has_target = MagicMock(return_value=True)
        with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
            self.assertEqual(alias.present(name, target), ret)

    def test_present_has_not_target_test(self):
        """
        test alias.present has't got target yet test mode
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Alias {0} -> {1} is set to be added".format(name, target),
            "changes": {},
            "name": name,
            "result": None,
        }

        has_target = MagicMock(return_value=False)
        with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
            with patch.dict(alias.__opts__, {"test": True}):
                self.assertEqual(alias.present(name, target), ret)

    def test_present_set_target(self):
        """
        test alias.present set target
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Set email alias {0} -> {1}".format(name, target),
            "changes": {"alias": name},
            "name": name,
            "result": True,
        }

        has_target = MagicMock(return_value=False)
        set_target = MagicMock(return_value=True)
        with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
            with patch.dict(alias.__opts__, {"test": False}):
                with patch.dict(alias.__salt__, {"aliases.set_target": set_target}):
                    self.assertEqual(alias.present(name, target), ret)

    def test_present_set_target_failed(self):
        """
        test alias.present set target failure
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Failed to set alias {0} -> {1}".format(name, target),
            "changes": {},
            "name": name,
            "result": False,
        }

        has_target = MagicMock(return_value=False)
        set_target = MagicMock(return_value=False)
        with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
            with patch.dict(alias.__opts__, {"test": False}):
                with patch.dict(alias.__salt__, {"aliases.set_target": set_target}):
                    self.assertEqual(alias.present(name, target), ret)

    def test_absent_already_gone(self):
        """
        test alias.absent already gone
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Alias {0} already absent".format(name),
            "changes": {},
            "name": name,
            "result": True,
        }

        get_target = MagicMock(return_value=False)
        with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
            self.assertEqual(alias.absent(name), ret)

    def test_absent_not_gone_test(self):
        """
        test alias.absent already gone test mode
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Alias {0} is set to be removed".format(name),
            "changes": {},
            "name": name,
            "result": None,
        }

        get_target = MagicMock(return_value=True)
        with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
            with patch.dict(alias.__opts__, {"test": True}):
                self.assertEqual(alias.absent(name), ret)

    def test_absent_rm_alias(self):
        """
        test alias.absent remove alias
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Removed alias {0}".format(name),
            "changes": {"alias": name},
            "name": name,
            "result": True,
        }

        get_target = MagicMock(return_value=True)
        rm_alias = MagicMock(return_value=True)
        with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
            with patch.dict(alias.__opts__, {"test": False}):
                with patch.dict(alias.__salt__, {"aliases.rm_alias": rm_alias}):
                    self.assertEqual(alias.absent(name), ret)

    def test_absent_rm_alias_failed(self):
        """
        test alias.absent remove alias failure
        """
        name = "saltdude"
        target = "dude@saltstack.com"
        ret = {
            "comment": "Failed to remove alias {0}".format(name),
            "changes": {},
            "name": name,
            "result": False,
        }

        get_target = MagicMock(return_value=True)
        rm_alias = MagicMock(return_value=False)
        with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
            with patch.dict(alias.__opts__, {"test": False}):
                with patch.dict(alias.__salt__, {"aliases.rm_alias": rm_alias}):
                    self.assertEqual(alias.absent(name), ret)
