# -*- coding: utf-8 -*-
"""
    :synopsis: Unit Tests for Windows iis Module 'state.win_iis'
    :platform: Windows
    .. versionadded:: 2019.2.2
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.win_iis as win_iis

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class WinIisTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.win_pki
    """

    def setup_loader_modules(self):
        return {win_iis: {}}

    def __base_webconfiguration_ret(
        self, comment="", changes=None, name="", result=None
    ):
        return {
            "name": name,
            "changes": changes if changes else {},
            "comment": comment,
            "result": result,
        }

    def test_webconfiguration_settings_no_settings(self):
        name = "IIS"
        settings = {}
        expected_ret = self.__base_webconfiguration_ret(
            name=name, comment="No settings to change provided.", result=True
        )
        actual_ret = win_iis.webconfiguration_settings(name, settings)
        self.assertEqual(expected_ret, actual_ret)

    def test_webconfiguration_settings_collection_failure(self):
        name = "IIS:\\"
        settings = {
            "system.applicationHost/sites": {
                "Collection[{name: site0}].logFile.directory": "C:\\logs\\iis\\site0",
            },
        }
        old_settings = [
            {
                "filter": "system.applicationHost/sites",
                "name": "Collection[{name: site0}].logFile.directory",
                "value": "C:\\logs\\iis\\old_site",
            }
        ]
        current_settings = old_settings
        new_settings = old_settings
        expected_ret = self.__base_webconfiguration_ret(
            name=name,
            result=False,
            changes={
                "changes": {
                    old_settings[0]["filter"]
                    + "."
                    + old_settings[0]["name"]: {
                        "old": old_settings[0]["value"],
                        "new": settings[old_settings[0]["filter"]][
                            old_settings[0]["name"]
                        ],
                    }
                },
                "failures": {
                    old_settings[0]["filter"]
                    + "."
                    + old_settings[0]["name"]: {
                        "old": old_settings[0]["value"],
                        "new": new_settings[0]["value"],
                    }
                },
            },
            comment="Some settings failed to change.",
        )
        with patch.dict(
            win_iis.__salt__,
            {
                "win_iis.get_webconfiguration_settings": MagicMock(
                    side_effect=[old_settings, current_settings, new_settings]
                ),
                "win_iis.set_webconfiguration_settings": MagicMock(return_value=True),
            },
        ), patch.dict(win_iis.__opts__, {"test": False}):
            actual_ret = win_iis.webconfiguration_settings(name, settings)
        self.assertEqual(expected_ret, actual_ret)

    def test_webconfiguration_settings_collection(self):
        name = "IIS:\\"
        settings = {
            "system.applicationHost/sites": {
                "Collection[{name: site0}].logFile.directory": "C:\\logs\\iis\\site0",
            },
        }
        old_settings = [
            {
                "filter": "system.applicationHost/sites",
                "name": "Collection[{name: site0}].logFile.directory",
                "value": "C:\\logs\\iis\\old_site",
            }
        ]
        current_settings = [
            {
                "filter": "system.applicationHost/sites",
                "name": "Collection[{name: site0}].logFile.directory",
                "value": "C:\\logs\\iis\\site0",
            }
        ]
        new_settings = current_settings
        expected_ret = self.__base_webconfiguration_ret(
            name=name,
            result=True,
            changes={
                old_settings[0]["filter"]
                + "."
                + old_settings[0]["name"]: {
                    "old": old_settings[0]["value"],
                    "new": new_settings[0]["value"],
                }
            },
            comment="Set settings to contain the provided values.",
        )
        with patch.dict(
            win_iis.__salt__,
            {
                "win_iis.get_webconfiguration_settings": MagicMock(
                    side_effect=[old_settings, current_settings, new_settings]
                ),
                "win_iis.set_webconfiguration_settings": MagicMock(return_value=True),
            },
        ), patch.dict(win_iis.__opts__, {"test": False}):
            actual_ret = win_iis.webconfiguration_settings(name, settings)
        self.assertEqual(expected_ret, actual_ret)
