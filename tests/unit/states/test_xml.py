# -*- coding: utf-8 -*-
"""
Test cases for xml state
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.xml as xml

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class XMLTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.xml
    """

    def setup_loader_modules(self):
        return {xml: {}}

    def test_value_already_present(self):
        """
        Test for existing value_present
        """

        name = "testfile.xml"
        xpath = ".//list[@id='1']"
        value = "test value"

        state_return = {
            "name": name,
            "changes": {},
            "result": True,
            "comment": "{0} is already present".format(value),
        }

        with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=value)}):
            self.assertDictEqual(xml.value_present(name, xpath, value), state_return)

    def test_value_update(self):
        """
        Test for updating value_present
        """

        name = "testfile.xml"
        xpath = ".//list[@id='1']"
        value = "test value"

        old_value = "not test value"

        state_return = {
            "name": name,
            "changes": {name: {"new": value, "old": old_value}},
            "result": True,
            "comment": "{0} updated".format(name),
        }

        with patch.dict(
            xml.__salt__, {"xml.get_value": MagicMock(return_value=old_value)}
        ):
            with patch.dict(
                xml.__salt__, {"xml.set_value": MagicMock(return_value=True)}
            ):
                self.assertDictEqual(
                    xml.value_present(name, xpath, value), state_return
                )

    def test_value_update_test(self):
        """
        Test for value_present test=True
        """

        name = "testfile.xml"
        xpath = ".//list[@id='1']"
        value = "test value"

        old_value = "not test value"

        state_return = {
            "name": name,
            "changes": {name: {"old": old_value, "new": value}},
            "result": None,
            "comment": "{0} will be updated".format(name),
        }

        with patch.dict(
            xml.__salt__, {"xml.get_value": MagicMock(return_value=old_value)}
        ):
            self.assertDictEqual(
                xml.value_present(name, xpath, value, test=True), state_return
            )

    def test_value_update_invalid_xpath(self):
        """
        Test for value_present invalid xpath
        """

        name = "testfile.xml"
        xpath = ".//list[@id='1']"
        value = "test value"

        state_return = {
            "name": name,
            "changes": {},
            "result": False,
            "comment": "xpath query {0} not found in {1}".format(xpath, name),
        }

        with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=False)}):
            self.assertDictEqual(
                xml.value_present(name, xpath, value, test=True), state_return
            )
