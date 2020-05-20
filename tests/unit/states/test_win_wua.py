# -*- coding: utf-8 -*-
"""
Test the win_wua state module
"""
# Import Python Libs
from __future__ import (  # Import Salt Libs
    absolute_import,
    print_function,
    unicode_literals,
)

import salt.states.win_wua as win_wua
import salt.utils.platform
import salt.utils.win_update as win_update
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

UPDATES_LIST = {
    "ca3bb521-a8ea-4e26-a563-2ad6e3108b9a": {
        "KBs": ["KB4481252"],
        "Installed": False,
        "Title": "Blank",
    },
    "07609d43-d518-4e77-856e-d1b316d1b8a8": {
        "KBs": ["KB925673"],
        "Installed": False,
        "Title": "Blank",
    },
    "fbaa5360-a440-49d8-a3b6-0c4fc7ecaa19": {
        "KBs": ["KB4481252"],
        "Installed": False,
        "Title": "Blank",
    },
    "a873372b-7a5c-443c-8022-cd59a550bef4": {
        "KBs": ["KB3193497"],
        "Installed": False,
        "Title": "Blank",
    },
    "14075cbe-822e-4004-963b-f50e08d45563": {
        "KBs": ["KB4540723"],
        "Installed": False,
        "Title": "Blank",
    },
    "d931e99c-4dda-4d39-9905-0f6a73f7195f": {
        "KBs": ["KB3193497"],
        "Installed": False,
        "Title": "Blank",
    },
    "afda9e11-44a0-4602-9e9b-423af11ecaed": {
        "KBs": ["KB4541329"],
        "Installed": False,
        "Title": "Blank",
    },
    "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {
        "KBs": ["KB3193497"],
        "Installed": False,
        "Title": "Blank",
    },
    "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
        "KBs": ["KB4052623"],
        "Installed": False,
        "Title": "Blank",
    },
    "0689e74b-54d1-4f55-a916-96e3c737db90": {
        "KBs": ["KB890830"],
        "Installed": False,
        "Title": "Blank",
    },
}


UPDATES_LIST_NONE = {}


UPDATES_SUMMARY = {"Installed": 10}


class Updates(object):
    def __init__(self):
        self.updates = []


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
class WinWuaTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test the functions in the win_wua.uptodate function
    """

    def setup_loader_modules(self):
        return {win_wua: {"__opts__": {"test": False}, "__env__": "base"}}

    def test_uptodate_no_updates(self):
        """
        Test uptodate function with no updates found.
        """
        expected = {
            "name": "NA",
            "changes": {},
            "result": True,
            "comment": "No updates found",
        }

        class NoUpdates(Updates):
            @staticmethod
            def updates():  # pylint: disable=method-hidden
                return UPDATES_LIST_NONE

            @staticmethod
            def count():
                return len(UPDATES_LIST_NONE)

        patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
        patch_win32com = patch("win32com.client.Dispatch", autospec=True)
        patch_win_update_agent = patch.object(
            salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
        )
        patch_win_update = patch.object(
            salt.utils.win_update, "Updates", autospec=True, return_value=NoUpdates()
        )

        with patch_winapi_com, patch_win32com, patch_win_update_agent, patch_win_update:
            result = win_wua.uptodate(name="NA")
            self.assertDictEqual(result, expected)

    def test_uptodate_testmode(self):
        """
        Test uptodate function in test=true mode.
        """
        expected = {
            "name": "NA",
            "changes": {},
            "result": None,
            "comment": "Updates will be installed:",
        }
        patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
        patch_win32com = patch("win32com.client.Dispatch", autospec=True)
        patch_win_update_agent = patch.object(
            salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
        )
        patch_opts = patch.dict(win_wua.__opts__, {"test": True})

        with patch_winapi_com, patch_win32com, patch_win_update_agent, patch_opts:
            wua = win_update.WindowsUpdateAgent(online=False)
            wua._updates = [MagicMock(IsInstalled=False, IsDownloaded=False)]
            result = win_wua.uptodate(name="NA")
            self.assertDictEqual(result, expected)

    def test_uptodate(self):
        """
        Test uptodate function with some updates found.
        """
        expected = {
            "name": "NA",
            "changes": {
                "failed": {
                    "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
                        "Title": "Blank...",
                        "KBs": ["KB4052623"],
                    }
                }
            },
            "result": False,
            "comment": "Updates failed",
        }

        updates_not_installed = {
            "afda9e11-44a0-4602-9e9b-423af11ecaed": {
                "KBs": ["KB4541329"],
                "Installed": False,
                "Title": "Blank",
            },
            "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {
                "KBs": ["KB3193497"],
                "Installed": False,
                "Title": "Blank",
            },
            "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
                "KBs": ["KB4052623"],
                "Installed": False,
                "Title": "Blank",
            },
            "eac02c07-d744-4892-b80f-312d045e4ccc": {
                "KBs": ["KB4052444"],
                "Installed": False,
                "Title": "Blank",
            },
        }
        fake_wua = MagicMock()
        fake_updates = MagicMock()
        fake_updates.list.return_value = updates_not_installed

        fake_wua_updates = MagicMock()
        fake_wua_updates.list.return_value = UPDATES_LIST
        fake_wua.updates.return_value = fake_wua_updates

        patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
        patch_win32 = patch("win32com.client.Dispatch", autospec=True)
        patch_wua = patch(
            "salt.utils.win_update.WindowsUpdateAgent",
            autospec=True,
            return_value=fake_wua,
        )
        patch_win_wua_update = patch(
            "salt.utils.win_update.Updates", autospec=True, return_value=fake_updates
        )
        patch_opts = patch.dict(win_wua.__opts__, {"test": False})

        with patch_winapi_com, patch_win32, patch_wua, patch_win_wua_update, patch_opts:
            wua = win_update.WindowsUpdateAgent(online=False)
            result = win_wua.uptodate(name="NA")
            self.assertDictEqual(result, expected)
