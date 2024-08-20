"""
Module for managing Windows Updates using the Windows Update Agent.

List updates on the system using the following functions:

- :py:func:`win_wua.available <salt.modules.win_wua.available>`
- :py:func:`win_wua.list <salt.modules.win_wua.list_>`

This is an easy way to find additional information about updates available to
to the system, such as the GUID, KB number, or description.

Once you have the GUID or a KB number for the update you can get information
about the update, download, install, or uninstall it using these functions:

- :py:func:`win_wua.get <salt.modules.win_wua.get>`
- :py:func:`win_wua.download <salt.modules.win_wua.download>`
- :py:func:`win_wua.install <salt.modules.win_wua.install>`
- :py:func:`win_wua.uninstall <salt.modules.win_wua.uninstall>`

The get function expects a name in the form of a GUID, KB, or Title and should
return information about a single update. The other functions accept either a
single item or a list of items for downloading/installing/uninstalling a
specific list of items.

The :py:func:`win_wua.list <salt.modules.win_wua.list_>` and
:py:func:`win_wua.get <salt.modules.win_wua.get>` functions are utility
functions. In addition to returning information about updates they can also
download and install updates by setting ``download=True`` or ``install=True``.
So, with py:func:`win_wua.list <salt.modules.win_wua.list_>` for example, you
could run the function with the filters you want to see what is available. Then
just add ``install=True`` to install everything on that list.

If you want to download, install, or uninstall specific updates, use
:py:func:`win_wua.download <salt.modules.win_wua.download>`,
:py:func:`win_wua.install <salt.modules.win_wua.install>`, or
:py:func:`win_wua.uninstall <salt.modules.win_wua.uninstall>`. To update your
system with the latest updates use :py:func:`win_wua.list
<salt.modules.win_wua.list_>` and set ``install=True``

You can also adjust the Windows Update settings using the
:py:func:`win_wua.set_wu_settings <salt.modules.win_wua.set_wu_settings>`
function. This function is only supported on the following operating systems:

- Windows Vista / Server 2008
- Windows 7 / Server 2008R2
- Windows 8 / Server 2012
- Windows 8.1 / Server 2012R2

As of Windows 10 and Windows Server 2016, the ability to modify the Windows
Update settings has been restricted. The settings can be modified in the Local
Group Policy using the ``lgpo`` module.

.. versionadded:: 2015.8.0

:depends: salt.utils.win_update
"""

import logging

import salt.utils.platform
import salt.utils.win_service
import salt.utils.win_update
import salt.utils.winapi
from salt.exceptions import CommandExecutionError

try:
    import win32com.client

    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

log = logging.getLogger(__name__)

__func_alias__ = {
    "list_": "list",
}


def __virtual__():
    """
    Only works on Windows systems with PyWin32
    """
    if not salt.utils.platform.is_windows():
        return False, "WUA: Only available on Windows systems"

    if not HAS_PYWIN32:
        return False, "WUA: Requires PyWin32 libraries"

    if not salt.utils.win_update.HAS_PYWIN32:
        return False, "WUA: Missing Libraries required by salt.utils.win_update"

    if salt.utils.win_service.info("wuauserv")["StartType"] == "Disabled":
        return (
            False,
            "WUA: The Windows Update service (wuauserv) must not be disabled",
        )

    if salt.utils.win_service.info("msiserver")["StartType"] == "Disabled":
        return (
            False,
            "WUA: The Windows Installer service (msiserver) must not be disabled",
        )

    if salt.utils.win_service.info("BITS")["StartType"] == "Disabled":
        return (
            False,
            "WUA: The Background Intelligent Transfer service (bits) must not "
            "be disabled",
        )

    if salt.utils.win_service.info("CryptSvc")["StartType"] == "Disabled":
        return (
            False,
            "WUA: The Cryptographic Services service (CryptSvc) must not be disabled",
        )

    if salt.utils.win_service.info("TrustedInstaller")["StartType"] == "Disabled":
        return (
            False,
            "WUA: The Windows Module Installer service (TrustedInstaller) must "
            "not be disabled",
        )

    return True


def available(
    software=True,
    drivers=True,
    summary=False,
    skip_installed=True,
    skip_hidden=True,
    skip_mandatory=False,
    skip_reboot=False,
    categories=None,
    severities=None,
    online=True,
):
    """
    .. versionadded:: 2017.7.0

    List updates that match the passed criteria. This allows for more filter
    options than :func:`list`. Good for finding a specific GUID or KB.

    Args:

        software (bool):
            Include software updates in the results. Default is ``True``

        drivers (bool):
            Include driver updates in the results. Default is ``True``

        summary (bool):
            - ``True``: Return a summary of updates available for each category.
            - ``False`` (default): Return a detailed list of available updates.

        skip_installed (bool):
            Skip updates that are already installed. Default is ``True``

        skip_hidden (bool):
            Skip updates that have been hidden. Default is ``True``

        skip_mandatory (bool):
            Skip mandatory updates. Default is ``False``

        skip_reboot (bool):
            Skip updates that require a reboot. Default is ``False``

        categories (list):
            Specify the categories to list. Must be passed as a list. All
            categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set ``drivers=True``)
            * Feature Packs
            * Security Updates
            * Update Rollups
            * Updates
            * Update Rollups
            * Windows 7
            * Windows 8.1
            * Windows 8.1 drivers
            * Windows 8.1 and later drivers
            * Windows Defender

        severities (list):
            Specify the severities to include. Must be passed as a list. All
            severities returned by default.

            Severities include the following:

            * Critical
            * Important

        online (bool):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is. Default is ``True``

            .. versionadded:: 3001

    Returns:

        dict: Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            Dict of Updates:
            {'<GUID>': {
                'Title': <title>,
                'KB': <KB>,
                'GUID': <the globally unique identifier for the update>,
                'Description': <description>,
                'Downloaded': <has the update been downloaded>,
                'Installed': <has the update been installed>,
                'Mandatory': <is the update mandatory>,
                'UserInput': <is user input required>,
                'EULAAccepted': <has the EULA been accepted>,
                'Severity': <update severity>,
                'NeedsReboot': <is the update installed and awaiting reboot>,
                'RebootBehavior': <will the update require a reboot>,
                'Categories': [
                    '<category 1>',
                    '<category 2>',
                    ... ]
            }}

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': {
                <category 1>: <total for that category>,
                <category 2>: <total for category 2>,
                ... }
            }

    CLI Examples:

    .. code-block:: bash

        # Normal Usage (list all software updates)
        salt '*' win_wua.available

        # List all updates with categories of Critical Updates and Drivers
        salt '*' win_wua.available categories=["Critical Updates","Drivers"]

        # List all Critical Security Updates
        salt '*' win_wua.available categories=["Security Updates"] severities=["Critical"]

        # List all updates with a severity of Critical
        salt '*' win_wua.available severities=["Critical"]

        # A summary of all available updates
        salt '*' win_wua.available summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.available categories=["Feature Packs","Windows 8.1"] summary=True
    """

    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent(online=online)

    # Look for available
    updates = wua.available(
        skip_hidden=skip_hidden,
        skip_installed=skip_installed,
        skip_mandatory=skip_mandatory,
        skip_reboot=skip_reboot,
        software=software,
        drivers=drivers,
        categories=categories,
        severities=severities,
    )

    # Return results as Summary or Details
    return updates.summary() if summary else updates.list()


def get(name, download=False, install=False, online=True):
    """
    .. versionadded:: 2017.7.0

    Returns details for the named update

    Args:

        name (str):
            The name of the update you're searching for. This can be the GUID, a
            KB number, or any part of the name of the update. GUIDs and KBs are
            preferred. Run ``list`` to get the GUID for the update you're
            looking for.

        download (bool):
            Download the update returned by this function. Run this function
            first to see if the update exists, then set ``download=True`` to
            download the update.

        install (bool):
            Install the update returned by this function. Run this function
            first to see if the update exists, then set ``install=True`` to
            install the update.

        online (bool):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is. Default is ``True``

            .. versionadded:: 3001

    Returns:

        dict:
            Returns a dict containing a list of updates that match the name if
            download and install are both set to False. Should usually be a
            single update, but can return multiple if a partial name is given.

        If download or install is set to true it will return the results of the
        operation.

        .. code-block:: cfg

            Dict of Updates:
            {'<GUID>': {
                'Title': <title>,
                'KB': <KB>,
                'GUID': <the globally unique identifier for the update>,
                'Description': <description>,
                'Downloaded': <has the update been downloaded>,
                'Installed': <has the update been installed>,
                'Mandatory': <is the update mandatory>,
                'UserInput': <is user input required>,
                'EULAAccepted': <has the EULA been accepted>,
                'Severity': <update severity>,
                'NeedsReboot': <is the update installed and awaiting reboot>,
                'RebootBehavior': <will the update require a reboot>,
                'Categories': [
                    '<category 1>',
                    '<category 2>',
                    ... ]
            }}

    CLI Examples:

    .. code-block:: bash

        # Recommended Usage using GUID without braces
        # Use this to find the status of a specific update
        salt '*' win_wua.get 12345678-abcd-1234-abcd-1234567890ab

        # Use the following if you don't know the GUID:

        # Using a KB number
        # Not all updates have an associated KB
        salt '*' win_wua.get KB3030298

        # Using part or all of the name of the update
        # Could possibly return multiple results
        # Not all updates have an associated KB
        salt '*' win_wua.get 'Microsoft Camera Codec Pack'
    """
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent(online=online)

    # Search for Update
    updates = wua.search(name)

    ret = {}

    # Download
    if download or install:
        ret["Download"] = wua.download(updates)

    # Install
    if install:
        ret["Install"] = wua.install(updates)

    return ret if ret else updates.list()


def list(
    software=True,
    drivers=False,
    summary=False,
    skip_installed=True,
    categories=None,
    severities=None,
    download=False,
    install=False,
    online=True,
):
    """
    .. versionadded:: 2017.7.0

    Returns a detailed list of available updates or a summary. If ``download``
    or ``install`` is ``True`` the same list will be downloaded and/or
    installed.

    Args:

        software (bool):
            Include software updates in the results. Default is ``True``

        drivers (bool):
            Include driver updates in the results. Default is ``False``

        summary (bool):
            - ``True``: Return a summary of updates available for each category.
            - ``False`` (default): Return a detailed list of available updates.

        skip_installed (bool):
            Skip installed updates in the results. Default is ``True``

        download (bool):
            (Overrides reporting functionality) Download the list of updates
            returned by this function. Run this function first with
            ``download=False`` to see what will be downloaded, then set
            ``download=True`` to download the updates. Default is ``False``

        install (bool):
            (Overrides reporting functionality) Install the list of updates
            returned by this function. Run this function first with
            ``install=False`` to see what will be installed, then set
            ``install=True`` to install the updates. Default is ``False``

        categories (list):
            Specify the categories to list. Must be passed as a list. All
            categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set ``drivers=True``)
            * Feature Packs
            * Security Updates
            * Update Rollups
            * Updates
            * Update Rollups
            * Windows 7
            * Windows 8.1
            * Windows 8.1 drivers
            * Windows 8.1 and later drivers
            * Windows Defender

        severities (list):
            Specify the severities to include. Must be passed as a list. All
            severities returned by default.

            Severities include the following:

            * Critical
            * Important

        online (bool):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is. Default is ``True``

            .. versionadded:: 3001

    Returns:

        dict: Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            Dict of Updates:
            {'<GUID>': {
                'Title': <title>,
                'KB': <KB>,
                'GUID': <the globally unique identifier for the update>,
                'Description': <description>,
                'Downloaded': <has the update been downloaded>,
                'Installed': <has the update been installed>,
                'Mandatory': <is the update mandatory>,
                'UserInput': <is user input required>,
                'EULAAccepted': <has the EULA been accepted>,
                'Severity': <update severity>,
                'NeedsReboot': <is the update installed and awaiting reboot>,
                'RebootBehavior': <will the update require a reboot>,
                'Categories': [
                    '<category 1>',
                    '<category 2>',
                    ... ]
            }}

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': {
                <category 1>: <total for that category>,
                <category 2>: <total for category 2>,
                ... }
            }

    CLI Examples:

    .. code-block:: bash

        # Normal Usage (list all software updates)
        salt '*' win_wua.list

        # List all updates with categories of Critical Updates and Drivers
        salt '*' win_wua.list categories=['Critical Updates','Drivers']

        # List all Critical Security Updates
        salt '*' win_wua.list categories=['Security Updates'] severities=['Critical']

        # List all updates with a severity of Critical
        salt '*' win_wua.list severities=['Critical']

        # A summary of all available updates
        salt '*' win_wua.list summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.list categories=['Feature Packs','Windows 8.1'] summary=True
    """
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent(online=online)

    # Search for Update
    updates = wua.available(
        skip_installed=skip_installed,
        software=software,
        drivers=drivers,
        categories=categories,
        severities=severities,
    )

    ret = {}

    # Download
    if download or install:
        ret["Download"] = wua.download(updates)

    # Install
    if install:
        ret["Install"] = wua.install(updates)

    if not ret:
        return updates.summary() if summary else updates.list()

    return ret


def installed(summary=False, kbs_only=False):
    """
    .. versionadded:: 3001

    Get a list of all updates that are currently installed on the system.

    .. note::

        This list may not necessarily match the Update History on the machine.
        This will only show the updates that apply to the current build of
        Windows. So, for example, the system may have shipped with Windows 10
        Build 1607. That machine received updates to the 1607 build. Later the
        machine was upgraded to a newer feature release, 1803 for example. Then
        more updates were applied. This will only return the updates applied to
        the 1803 build and not those applied when the system was at the 1607
        build.

    Args:

        summary (bool):
            Return a summary instead of a detailed list of updates. ``True``
            will return a Summary, ``False`` will return a detailed list of
            installed updates. Default is ``False``

        kbs_only (bool):
            Only return a list of KBs installed on the system. If this parameter
            is passed, the ``summary`` parameter will be ignored. Default is
            ``False``

    Returns:
        dict:
            Returns a dictionary of either a Summary or a detailed list of
            updates installed on the system when ``kbs_only=False``

        list:
            Returns a list of KBs installed on the system when ``kbs_only=True``

    CLI Examples:

    .. code-block:: bash

        # Get a detailed list of all applicable updates installed on the system
        salt '*' win_wua.installed

        # Get a summary of all applicable updates installed on the system
        salt '*' win_wua.installed summary=True

        # Get a simple list of KBs installed on the system
        salt '*' win_wua.installed kbs_only=True
    """
    # Create a Windows Update Agent instance. Since we're only listing installed
    # updates, there's no need to go online to update the Windows Update db
    wua = salt.utils.win_update.WindowsUpdateAgent(online=False)
    updates = wua.installed()  # Get installed Updates objects
    results = updates.list()  # Convert to list

    if kbs_only:
        list_kbs = set()
        for item in results:
            list_kbs.update(results[item]["KBs"])
        return sorted(list_kbs)

    return updates.summary() if summary else results


def download(names):
    """
    .. versionadded:: 2017.7.0

    Downloads updates that match the list of passed identifiers. It's easier to
    use this function by using list_updates and setting ``download=True``.

    Args:

        names (str, list):
            A single update or a list of updates to download. This can be any
            combination of GUIDs, KB numbers, or names. GUIDs or KBs are
            preferred.

            .. note::

                An error will be raised if there are more results than there are
                items in the names parameter

    Returns:

        dict: A dictionary containing the details about the downloaded updates

    CLI Example:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.download names=['12345678-abcd-1234-abcd-1234567890ab', 'KB2131233']
    """
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Update
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError("No updates found")

    # Make sure it's a list so count comparison is correct
    if isinstance(names, str):
        names = [names]

    if isinstance(names, int):
        names = [str(names)]

    if updates.count() > len(names):
        raise CommandExecutionError(
            "Multiple updates found, names need to be more specific"
        )

    return wua.download(updates)


def install(names):
    """
    .. versionadded:: 2017.7.0

    Installs updates that match the list of identifiers. It may be easier to use
    the list_updates function and set ``install=True``.

    Args:

        names (str, list):
            A single update or a list of updates to install. This can be any
            combination of GUIDs, KB numbers, or names. GUIDs or KBs are
            preferred.

    .. note::

        An error will be raised if there are more results than there are items
        in the names parameter

    Returns:

        dict: A dictionary containing the details about the installed updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.install KB12323211
    """
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Updates
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError("No updates found")

    # Make sure it's a list so count comparison is correct
    if isinstance(names, str):
        names = [names]

    if isinstance(names, int):
        names = [str(names)]

    if updates.count() > len(names):
        raise CommandExecutionError(
            "Multiple updates found, names need to be more specific"
        )

    return wua.install(updates)


def uninstall(names):
    """
    .. versionadded:: 2017.7.0

    Uninstall updates.

    Args:

        names (str, list):
            A single update or a list of updates to uninstall. This can be any
            combination of GUIDs, KB numbers, or names. GUIDs or KBs are
            preferred.

    Returns:

        dict: A dictionary containing the details about the uninstalled updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.uninstall KB3121212

        # As a list
        salt '*' win_wua.uninstall guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB1231231']
    """
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Updates
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError("No updates found")

    return wua.uninstall(updates)


def set_wu_settings(
    level=None,
    recommended=None,
    featured=None,
    elevated=None,
    msupdate=None,
    day=None,
    time=None,
):
    """
    Change Windows Update settings. If no parameters are passed, the current
    value will be returned.

    Supported:
        - Windows Vista / Server 2008
        - Windows 7 / Server 2008R2
        - Windows 8 / Server 2012
        - Windows 8.1 / Server 2012R2

    .. note:
        Microsoft began using the Unified Update Platform (UUP) starting with
        Windows 10 / Server 2016. The Windows Update settings have changed and
        the ability to 'Save' Windows Update settings has been removed. Windows
        Update settings are read-only. See MSDN documentation:
        https://msdn.microsoft.com/en-us/library/aa385829(v=vs.85).aspx

    Args:

        level (int):
            Number from 1 to 4 indicating the update level:

            1. Never check for updates
            2. Check for updates but let me choose whether to download and
               install them
            3. Download updates but let me choose whether to install them
            4. Install updates automatically

        recommended (bool):
            Boolean value that indicates whether to include optional or
            recommended updates when a search for updates and installation of
            updates is performed.

        featured (bool):
            Boolean value that indicates whether to display notifications for
            featured updates.

        elevated (bool):
            Boolean value that indicates whether non-administrators can perform
            some update-related actions without administrator approval.

        msupdate (bool):
            Boolean value that indicates whether to turn on Microsoft Update for
            other Microsoft products

        day (str):
            Days of the week on which Automatic Updates installs or uninstalls
            updates. Accepted values:

            - Everyday
            - Monday
            - Tuesday
            - Wednesday
            - Thursday
            - Friday
            - Saturday

        time (str):
            Time at which Automatic Updates installs or uninstalls updates. Must
            be in the ##:## 24hr format, eg. 3:00 PM would be 15:00. Must be in
            1 hour increments.

    Returns:

        dict: Returns a dictionary containing the results.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.set_wu_settings level=4 recommended=True featured=False
    """
    # The AutomaticUpdateSettings.Save() method used in this function does not
    # work on Windows 10 / Server 2016. It is called in throughout this function
    # like this:
    #
    # with salt.utils.winapi.Com():
    #     obj_au = win32com.client.Dispatch('Microsoft.Update.AutoUpdate')
    #     obj_au_settings = obj_au.Settings
    #     obj_au_settings.Save()
    #
    # The `Save()` method reports success but doesn't actually change anything.
    # Windows Update settings are read-only in Windows 10 / Server 2016. There's
    # a little blurb on MSDN that mentions this, but gives no alternative for
    # changing these settings in Windows 10 / Server 2016.
    #
    # https://msdn.microsoft.com/en-us/library/aa385829(v=vs.85).aspx
    #
    # Apparently the Windows Update framework in Windows Vista - Windows 8.1 has
    # been changed quite a bit in Windows 10 / Server 2016. It is now called the
    # Unified Update Platform (UUP). I haven't found an API or a Powershell
    # commandlet for working with the UUP. Perhaps there will be something
    # forthcoming. The `win_lgpo` module might be an option for changing the
    # Windows Update settings using local group policy.
    ret = {"Success": True}

    # Initialize the PyCom system
    with salt.utils.winapi.Com():

        # Create an AutoUpdate object
        obj_au = win32com.client.Dispatch("Microsoft.Update.AutoUpdate")

        # Create an AutoUpdate Settings Object
        obj_au_settings = obj_au.Settings

    # Only change the setting if it's passed
    if level is not None:
        obj_au_settings.NotificationLevel = int(level)
        result = obj_au_settings.Save()
        if result is None:
            ret["Level"] = level
        else:
            ret["Comment"] = "Settings failed to save. Check permissions."
            ret["Success"] = False

    if recommended is not None:
        obj_au_settings.IncludeRecommendedUpdates = recommended
        result = obj_au_settings.Save()
        if result is None:
            ret["Recommended"] = recommended
        else:
            ret["Comment"] = "Settings failed to save. Check permissions."
            ret["Success"] = False

    if featured is not None:
        obj_au_settings.FeaturedUpdatesEnabled = featured
        result = obj_au_settings.Save()
        if result is None:
            ret["Featured"] = featured
        else:
            ret["Comment"] = "Settings failed to save. Check permissions."
            ret["Success"] = False

    if elevated is not None:
        obj_au_settings.NonAdministratorsElevated = elevated
        result = obj_au_settings.Save()
        if result is None:
            ret["Elevated"] = elevated
        else:
            ret["Comment"] = "Settings failed to save. Check permissions."
            ret["Success"] = False

    if day is not None:
        # Check that day is valid
        days = {
            "Everyday": 0,
            "Sunday": 1,
            "Monday": 2,
            "Tuesday": 3,
            "Wednesday": 4,
            "Thursday": 5,
            "Friday": 6,
            "Saturday": 7,
        }
        if day not in days:
            ret["Comment"] = (
                "Day needs to be one of the following: Everyday, "
                "Monday, Tuesday, Wednesday, Thursday, Friday, "
                "Saturday"
            )
            ret["Success"] = False
        else:
            # Set the numeric equivalent for the day setting
            obj_au_settings.ScheduledInstallationDay = days[day]
            result = obj_au_settings.Save()
            if result is None:
                ret["Day"] = day
            else:
                ret["Comment"] = "Settings failed to save. Check permissions."
                ret["Success"] = False

    if time is not None:
        # Check for time as a string: if the time is not quoted, yaml will
        # treat it as an integer
        if not isinstance(time, str):
            ret["Comment"] = (
                "Time argument needs to be a string; it may need to "
                "be quoted. Passed {}. Time not set.".format(time)
            )
            ret["Success"] = False
        # Check for colon in the time
        elif ":" not in time:
            ret["Comment"] = (
                "Time argument needs to be in 00:00 format. "
                "Passed {}. Time not set.".format(time)
            )
            ret["Success"] = False
        else:
            # Split the time by :
            t = time.split(":")
            # We only need the hours value
            obj_au_settings.FeaturedUpdatesEnabled = t[0]
            result = obj_au_settings.Save()
            if result is None:
                ret["Time"] = time
            else:
                ret["Comment"] = "Settings failed to save. Check permissions."
                ret["Success"] = False

    if msupdate is not None:
        # Microsoft Update requires special handling
        # First load the MS Update Service Manager
        with salt.utils.winapi.Com():
            obj_sm = win32com.client.Dispatch("Microsoft.Update.ServiceManager")

            # Give it a bogus name
            obj_sm.ClientApplicationID = "My App"

            if msupdate:
                # msupdate is true, so add it to the services
                try:
                    obj_sm.AddService2("7971f918-a847-4430-9279-4a52d1efe18d", 7, "")
                    ret["msupdate"] = msupdate
                except Exception as error:  # pylint: disable=broad-except
                    # pylint: disable=unpacking-non-sequence,unbalanced-tuple-unpacking
                    (
                        hr,
                        msg,
                        exc,
                        arg,
                    ) = error.args
                    # pylint: enable=unpacking-non-sequence,unbalanced-tuple-unpacking
                    # Consider checking for -2147024891 (0x80070005) Access Denied
                    ret["Comment"] = f"Failed with failure code: {exc[5]}"
                    ret["Success"] = False
            else:
                # msupdate is false, so remove it from the services
                # check to see if the update is there or the RemoveService function
                # will fail
                if _get_msupdate_status():
                    # Service found, remove the service
                    try:
                        obj_sm.RemoveService("7971f918-a847-4430-9279-4a52d1efe18d")
                        ret["msupdate"] = msupdate
                    except Exception as error:  # pylint: disable=broad-except
                        # pylint: disable=unpacking-non-sequence,unbalanced-tuple-unpacking
                        (
                            hr,
                            msg,
                            exc,
                            arg,
                        ) = error.args
                        # pylint: enable=unpacking-non-sequence,unbalanced-tuple-unpacking
                        # Consider checking for the following
                        # -2147024891 (0x80070005) Access Denied
                        # -2145091564 (0x80248014) Service Not Found (shouldn't get
                        # this with the check for _get_msupdate_status above
                        ret["Comment"] = f"Failed with failure code: {exc[5]}"
                        ret["Success"] = False
                else:
                    ret["msupdate"] = msupdate

    ret["Reboot"] = get_needs_reboot()

    return ret


def get_wu_settings():
    """
    Get current Windows Update settings.

    Returns:

        dict: A dictionary of Windows Update settings:

        Featured Updates:
            Boolean value that indicates whether to display notifications for
            featured updates.

        Group Policy Required (Read-only):
            Boolean value that indicates whether Group Policy requires the
            Automatic Updates service.

        Microsoft Update:
            Boolean value that indicates whether to turn on Microsoft Update for
            other Microsoft Products

        Needs Reboot:
            Boolean value that indicates whether the machine is in a reboot
            pending state.

        Non Admins Elevated:
            Boolean value that indicates whether non-administrators can perform
            some update-related actions without administrator approval.

        Notification Level:

            Number 1 to 4 indicating the update level:

                1. Never check for updates
                2. Check for updates but let me choose whether to download and
                   install them
                3. Download updates but let me choose whether to install them
                4. Install updates automatically

        Read Only (Read-only):
            Boolean value that indicates whether the Automatic Update
            settings are read-only.

        Recommended Updates:
            Boolean value that indicates whether to include optional or
            recommended updates when a search for updates and installation of
            updates is performed.

        Scheduled Day:
            Days of the week on which Automatic Updates installs or uninstalls
            updates.

        Scheduled Time:
            Time at which Automatic Updates installs or uninstalls updates.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.get_wu_settings
    """
    ret = {}

    day = [
        "Every Day",
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]

    # Initialize the PyCom system
    with salt.utils.winapi.Com():
        # Create an AutoUpdate object
        obj_au = win32com.client.Dispatch("Microsoft.Update.AutoUpdate")

        # Create an AutoUpdate Settings Object
        obj_au_settings = obj_au.Settings

        # Populate the return dictionary
        ret["Featured Updates"] = obj_au_settings.FeaturedUpdatesEnabled
        ret["Group Policy Required"] = obj_au_settings.Required
        ret["Microsoft Update"] = _get_msupdate_status()
        ret["Needs Reboot"] = get_needs_reboot()
        ret["Non Admins Elevated"] = obj_au_settings.NonAdministratorsElevated
        ret["Notification Level"] = obj_au_settings.NotificationLevel
        ret["Read Only"] = obj_au_settings.ReadOnly
        ret["Recommended Updates"] = obj_au_settings.IncludeRecommendedUpdates
        ret["Scheduled Day"] = day[obj_au_settings.ScheduledInstallationDay]
        # Scheduled Installation Time requires special handling to return the time
        # in the right format
        if obj_au_settings.ScheduledInstallationTime < 10:
            ret["Scheduled Time"] = "0{}:00".format(
                obj_au_settings.ScheduledInstallationTime
            )
        else:
            ret["Scheduled Time"] = "{}:00".format(
                obj_au_settings.ScheduledInstallationTime
            )

    return ret


def _get_msupdate_status():
    """
    Check to see if Microsoft Update is Enabled
    Return Boolean
    """
    # To get the status of Microsoft Update we actually have to check the
    # Microsoft Update Service Manager
    # Initialize the PyCom system
    with salt.utils.winapi.Com():
        # Create a ServiceManager Object
        obj_sm = win32com.client.Dispatch("Microsoft.Update.ServiceManager")

        # Return a collection of loaded Services
        col_services = obj_sm.Services

        # Loop through the collection to find the Microsoft Udpate Service
        # If it exists return True otherwise False
        for service in col_services:
            if service.name == "Microsoft Update":
                return True

    return False


def get_needs_reboot():
    """
    Determines if the system needs to be rebooted.

    Returns:

        bool: ``True`` if the system requires a reboot, otherwise ``False``

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.get_needs_reboot
    """
    return salt.utils.win_update.needs_reboot()
