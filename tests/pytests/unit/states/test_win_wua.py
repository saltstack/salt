"""
Test the win_wua state module
"""

from collections import namedtuple

import pytest

import salt.states.win_wua as win_wua
import salt.utils.platform
import salt.utils.win_update as win_update
from tests.support.mock import MagicMock, patch


@pytest.fixture
def updates_list():
    updated_list = {
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
            "KBs": ["KB3193498"],
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
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
        "0689e74b-54d1-4f55-a916-96e3c737db90": {
            "KBs": ["KB890830"],
            "Installed": False,
            "Title": "Blank",
        },
    }
    return updated_list


@pytest.fixture
def updates_list_none():
    updates_list_empty = {}
    return updates_list_empty


@pytest.fixture
def updates_summary():
    updates_summary_d = {"Installed": 10}
    return updates_summary_d


class Updates:
    def __init__(self):
        self.updates = []


@pytest.fixture
def configure_loader_modules():
    return {win_wua: {"__opts__": {"test": False}, "__env__": "base"}}


@pytest.fixture
def update_records():
    return namedtuple(
        "UpdateRecord",
        ["KBArticleIDs", "Identity", "IsDownloaded", "IsInstalled", "Title"],
    )


@pytest.fixture
def update_records_identity():
    return namedtuple("UpdateRecordIdentity", "UpdateID")


@pytest.mark.skip_unless_on_windows
def test_uptodate_no_updates(updates_list_none):
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
            return updates_list_none

        @staticmethod
        def count():
            return len(updates_list_none)

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
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_uptodate_test_mode():
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
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_uptodate(updates_list):
    """
    Test uptodate function with some updates found.
    """
    expected = {
        "name": "NA",
        "changes": {
            "failed": {
                "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {
                    "KBs": ["KB3193497"],
                    "Title": "Blank",
                },
                "afda9e11-44a0-4602-9e9b-423af11ecaed": {
                    "KBs": ["KB4541329"],
                    "Title": "Blank",
                },
                "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
                    "KBs": ["KB4052623"],
                    "Title": "KB4052623: Really long title that exceeds 40 characters",
                },
            },
            "superseded": {
                "eac02c07-d744-4892-b80f-312d045e4ccc": {
                    "KBs": ["KB4052444"],
                    "Title": "Superseded Update",
                }
            },
        },
        "result": False,
        "comment": "Some updates failed to install\nSome updates were superseded",
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
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
        "eac02c07-d744-4892-b80f-312d045e4ccc": {
            "KBs": ["KB4052444"],
            "Installed": False,
            "Title": "Superseded Update",
        },
    }

    fake_updates = MagicMock()
    fake_updates.list.return_value = updates_not_installed

    patch_win_wua_update = patch(
        "salt.utils.win_update.Updates",
        autospec=True,
        return_value=fake_updates,
    )

    fake_wua_updates = MagicMock()
    fake_wua_updates.list.return_value = updates_list

    fake_wua = MagicMock()
    fake_wua.updates.return_value = fake_wua_updates
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=fake_wua,
    )

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_win32 = patch("win32com.client.Dispatch", autospec=True)
    patch_opts = patch.dict(win_wua.__opts__, {"test": False})

    with patch_winapi_com, patch_win32, patch_wua, patch_win_wua_update, patch_opts:
        result = win_wua.uptodate(name="NA")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_installed(update_records, update_records_identity):
    """
    Test installed function
    """

    update_search_obj = {
        update_records(
            KBArticleIDs=("4052623",),
            Identity=update_records_identity(
                UpdateID="eac02b09-d745-4891-b80f-400e0e5e4b6d"
            ),
            IsDownloaded=False,
            IsInstalled=False,
            Title="KB4052623: Really long title that exceeds 40 characters",
        ),
    }

    update_search_dict = {
        "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
            "Downloaded": True,
            "KBs": ["KB4052623"],
            "Installed": True,
            "NeedsReboot": True,
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
    }

    updates_refresh = {
        "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {
            "Downloaded": False,
            "KBs": ["KB3193497"],
            "Installed": False,
            "NeedsReboot": False,
            "Title": "Update 1",
        },
        "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
            "Downloaded": True,
            "KBs": ["KB4052623"],
            "Installed": True,
            "NeedsReboot": True,
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
        "eac02c07-d744-4892-b80f-312d045e4ccc": {
            "Downloaded": True,
            "KBs": ["KB4052444"],
            "Installed": True,
            "NeedsReboot": False,
            "Title": "Update 3",
        },
    }

    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 1
    # Mocks the the updates collection object
    mock_wua.search().updates = update_search_obj

    # This mocks the updates collection in the install variable. This will
    # get populated to as matches are found with the Add method
    mock_updates = MagicMock()
    # Needs to return the number of updates that need to be installed
    # (IsInstalled = False)
    mock_updates.count.return_value = 1
    # Returns the updates that need to be installed as a dict
    mock_updates.list.return_value = update_search_dict

    # This gives us post_info
    mock_wua.updates = MagicMock()
    # Mock a refresh of the updates recognized by the machine. This would
    # occur post install. This is compared with the updates on the machine
    # to determine if the update was successful
    mock_wua.updates().list.return_value = updates_refresh

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )
    patch_update_collection = patch(
        "salt.utils.win_update.Updates", autospec=True, return_value=mock_updates
    )
    patch_opts = patch.dict(win_wua.__opts__, {"test": False})

    with (
        patch_winapi_com
    ), patch_dispatch, patch_wua, patch_update_collection, patch_opts:
        expected = {
            "changes": {
                "installed": {
                    "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
                        "KBs": ["KB4052623"],
                        "NeedsReboot": True,
                        "Title": "KB4052623: Really long title that exceeds 40 characters",
                    }
                }
            },
            "comment": "Updates installed successfully",
            "name": "KB4062623",
            "result": True,
        }
        result = win_wua.installed(name="KB4062623")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_installed_no_updates():
    """
    Test installed function when no updates are found.
    """
    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 0

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )

    with patch_winapi_com, patch_dispatch, patch_wua:
        expected = {
            "name": "KB4062623",
            "changes": {},
            "result": True,
            "comment": "No updates found",
        }
        result = win_wua.installed(name="KB4062623")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_installed_test_mode(update_records, update_records_identity):
    """
    Test installed function in test mode
    """

    update_search_obj = {
        update_records(
            KBArticleIDs=("4052623",),
            Identity=update_records_identity(
                UpdateID="eac02b09-d745-4891-b80f-400e0e5e4b6d"
            ),
            IsDownloaded=False,
            IsInstalled=False,
            Title="Update 2",
        ),
    }

    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 1
    # Mocks the the updates collection object
    mock_wua.search().updates = update_search_obj

    # This mocks the updates collection in the install variable. This will
    # get populated to as matches are found with the Add method
    mock_updates = MagicMock()
    # Needs to return the number of updates that need to be installed
    # (IsInstalled = False)
    mock_updates.count.return_value = 1

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )
    patch_update_collection = patch(
        "salt.utils.win_update.Updates", autospec=True, return_value=mock_updates
    )
    patch_opts = patch.dict(win_wua.__opts__, {"test": True})

    with (
        patch_winapi_com
    ), patch_dispatch, patch_wua, patch_update_collection, patch_opts:
        expected = {
            "changes": {},
            "comment": "Updates will be installed:",
            # I don't know how to mock this part so the list will show up.
            # It's an update collection object populated using the Add
            # method. But this works for now
            "name": "KB4062623",
            "result": None,
        }
        result = win_wua.installed(name="KB4062623")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_installed_already_installed(update_records, update_records_identity):
    """
    Test installed function when the update is already installed
    """

    update_search_obj = {
        update_records(
            KBArticleIDs=("4052623",),
            Identity=update_records_identity(
                UpdateID="eac02b09-d745-4891-b80f-400e0e5e4b6d"
            ),
            IsDownloaded=True,
            IsInstalled=True,
            Title="Update 2",
        ),
    }

    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 1
    # Mocks the the updates collection object
    mock_wua.search().updates = update_search_obj

    # This mocks the updates collection in the install variable. This will
    # get populated to as matches are found with the Add method
    mock_updates = MagicMock()
    # Needs to return the number of updates that need to be installed
    # (IsInstalled = False)
    mock_updates.count.return_value = 0

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )
    patch_update_collection = patch(
        "salt.utils.win_update.Updates", autospec=True, return_value=mock_updates
    )
    patch_opts = patch.dict(win_wua.__opts__, {"test": True})

    with (
        patch_winapi_com
    ), patch_dispatch, patch_wua, patch_update_collection, patch_opts:
        expected = {
            "changes": {},
            "comment": "Updates already installed: KB4052623",
            "name": "KB4062623",
            "result": True,
        }
        result = win_wua.installed(name="KB4062623")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_removed(update_records, update_records_identity):
    """
    Test removed function
    """

    update_search_obj = {
        update_records(
            KBArticleIDs=("4052623",),
            Identity=update_records_identity(
                UpdateID="eac02b09-d745-4891-b80f-400e0e5e4b6d"
            ),
            IsDownloaded=False,
            IsInstalled=True,
            Title="KB4052623: Really long title that exceeds 40 characters",
        ),
    }

    update_search_dict = {
        "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
            "Downloaded": True,
            "KBs": ["KB4052623"],
            "Installed": False,
            "NeedsReboot": True,
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
    }

    updates_refresh = {
        "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {
            "Downloaded": False,
            "KBs": ["KB3193497"],
            "Installed": False,
            "NeedsReboot": False,
            "Title": "Update 1",
        },
        "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
            "Downloaded": True,
            "KBs": ["KB4052623"],
            "Installed": False,
            "NeedsReboot": True,
            "Title": "KB4052623: Really long title that exceeds 40 characters",
        },
        "eac02c07-d744-4892-b80f-312d045e4ccc": {
            "Downloaded": True,
            "KBs": ["KB4052444"],
            "Installed": True,
            "NeedsReboot": False,
            "Title": "Update 3",
        },
    }

    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 1
    # Mocks the the updates collection object
    mock_wua.search().updates = update_search_obj

    # This mocks the updates collection in the uninstall variable. This will
    # get populated as matches are found with the Add method
    mock_updates = MagicMock()
    # Needs to return the number of updates that need to be installed
    # (IsInstalled = False)
    mock_updates.count.return_value = 1
    # Returns the updates that need to be installed as a dict
    mock_updates.list.return_value = update_search_dict

    # This gives us post_info
    mock_wua.updates = MagicMock()
    # Mock a refresh of the updates recognized by the machine. This would
    # occur post uninstall. This is compared with the updates on the machine
    # to determine if the removal was successful
    mock_wua.updates().list.return_value = updates_refresh

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )
    patch_update_collection = patch(
        "salt.utils.win_update.Updates", autospec=True, return_value=mock_updates
    )
    patch_opts = patch.dict(win_wua.__opts__, {"test": False})

    with (
        patch_winapi_com
    ), patch_dispatch, patch_wua, patch_update_collection, patch_opts:
        expected = {
            "changes": {
                "removed": {
                    "eac02b09-d745-4891-b80f-400e0e5e4b6d": {
                        "KBs": ["KB4052623"],
                        "NeedsReboot": True,
                        "Title": "KB4052623: Really long title that exceeds 40 characters",
                    }
                }
            },
            "comment": "Updates removed successfully",
            "name": "KB4062623",
            "result": True,
        }
        result = win_wua.removed(name="KB4062623")
        assert result == expected


@pytest.mark.skip_unless_on_windows
def test_removed_test_mode(update_records, update_records_identity):
    """
    Test removed function in test mode
    """

    update_search_obj = {
        update_records(
            KBArticleIDs=("4052623",),
            Identity=update_records_identity(
                UpdateID="eac02b09-d745-4891-b80f-400e0e5e4b6d"
            ),
            IsDownloaded=False,
            IsInstalled=True,
            Title="KB4052623: Really long title that exceeds 40 characters",
        ),
    }

    # Mocks the connection to the Windows Update Agent
    mock_wua = MagicMock()
    # Mocks the initial search
    mock_wua.search = MagicMock()
    # Mocks the number of updates found.
    mock_wua.search().count.return_value = 1
    # Mocks the the updates collection object
    mock_wua.search().updates = update_search_obj

    # This mocks the updates collection in the install variable. This will
    # get populated to as matches are found with the Add method
    mock_updates = MagicMock()
    # Needs to return the number of updates that need to be installed
    # (IsInstalled = False)
    mock_updates.count.return_value = 1

    patch_winapi_com = patch("salt.utils.winapi.Com", autospec=True)
    patch_dispatch = patch("win32com.client.Dispatch", autospec=True)
    patch_wua = patch(
        "salt.utils.win_update.WindowsUpdateAgent",
        autospec=True,
        return_value=mock_wua,
    )
    patch_update_collection = patch(
        "salt.utils.win_update.Updates", autospec=True, return_value=mock_updates
    )
    patch_opts = patch.dict(win_wua.__opts__, {"test": True})

    with (
        patch_winapi_com
    ), patch_dispatch, patch_wua, patch_update_collection, patch_opts:
        expected = {
            "changes": {},
            "comment": "Updates will be removed:",
            # I don't know how to mock this part so the list will show up.
            # It's an update collection object populated using the Add
            # method. But this works for now
            "name": "KB4062623",
            "result": None,
        }
        result = win_wua.removed(name="KB4062623")
        assert result == expected
