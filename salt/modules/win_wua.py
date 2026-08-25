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

.. note::

    **Troubleshooting an update that reports success but doesn't persist**

    If :py:func:`win_wua.install <salt.modules.win_wua.install>` reports
    success but the update does not appear installed after a reboot, start
    with :py:func:`win_wua.get_needs_reboot
    <salt.modules.win_wua.get_needs_reboot>` to make sure no reboot is
    already pending (installing/resetting while a reboot is pending can
    itself be the cause). Next use :py:func:`win_wua.get_cbs_log
    <salt.modules.win_wua.get_cbs_log>` and :py:func:`win_wua.get_windows_update_log
    <salt.modules.win_wua.get_windows_update_log>` to look for the
    underlying servicing-stack (CBS) or Windows Update Agent error --
    ``install()``'s return value only reflects the installer job's result
    at call time, not whether the update actually persisted through a
    required reboot. To confirm persistence, re-run
    :py:func:`win_wua.installed <salt.modules.win_wua.installed>` or
    :py:func:`win_wua.get <salt.modules.win_wua.get>` after the reboot
    completes and compare against what was requested. Only after the logs
    point at WUA datastore/catalog-cache corruption specifically should you
    reach for :py:func:`win_wua.reset <salt.modules.win_wua.reset>` (or
    :py:func:`win_wua.reset_datastore <salt.modules.win_wua.reset_datastore>`
    / :py:func:`win_wua.reset_catroot <salt.modules.win_wua.reset_catroot>`)
    as a troubleshooting last resort -- these do not fix component-store
    (CBS)-level rejections, which require ``DISM /Cleanup-Image
    /RestoreHealth`` instead.

.. versionadded:: 2015.8.0

:depends: salt.utils.win_update
"""

import logging
import os
import shutil
import tempfile
import time

import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.win_pwsh
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

# Services stopped/started (in this order) when resetting the WU datastore
# or catalog cache. TrustedInstaller is intentionally excluded: it is
# trigger-started by Windows and should not be manually stopped/started.
_WU_SERVICES = ("wuauserv", "CryptSvc", "BITS", "msiserver")


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

        software (:obj:`bool`, optional):
            Include software updates in the results.

            Default is ``True``.

        drivers (:obj:`bool`, optional):
            Include driver updates in the results.

            Default is ``True``.

        summary (:obj:`bool`, optional):
            - ``True``: Return a summary of updates available for each category.
            - ``False`` (default): Return a detailed list of available updates.

            Default is ``False``.

        skip_installed (:obj:`bool`, optional):
            Skip updates that are already installed.

            Default is ``True``.

        skip_hidden (:obj:`bool`, optional):
            Skip updates that have been hidden.

            Default is ``True``.

        skip_mandatory (:obj:`bool`, optional):
            Skip mandatory updates.

            Default is ``False``.

        skip_reboot (:obj:`bool`, optional):
            Skip updates that require a reboot.

            Default is ``False``.

        categories (:obj:`list`, optional):
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

            Default is ``None``.

        severities (:obj:`list`, optional):
            Specify the severities to include. Must be passed as a list. All
            severities returned by default.

            Severities include the following:

            * Critical
            * Important

            Default is ``None``.

        online (:obj:`bool`, optional):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is. Default is ``True``

            .. versionadded:: 3001

            Default is ``True``.

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
        salt '*' win_wua.available categories='["Critical Updates","Drivers"]'

        # List all Critical Security Updates
        salt '*' win_wua.available categories='["Security Updates"]' severities='["Critical"]'

        # List all updates with a severity of Critical
        salt '*' win_wua.available severities='["Critical"]'

        # A summary of all available updates
        salt '*' win_wua.available summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.available categories='["Feature Packs","Windows 8.1"]' summary=True
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

        download (:obj:`bool`, optional):
            Download the update returned by this function. Run this function
            first to see if the update exists, then set ``download=True`` to
            download the update.

            Default is ``False``.

        install (:obj:`bool`, optional):
            Install the update returned by this function. Run this function
            first to see if the update exists, then set ``install=True`` to
            install the update.

            Default is ``False``.

        online (:obj:`bool`, optional):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is.

            Default is ``True``.

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

        software (:obj:`bool`, optional):
            Include software updates in the results.

            Default is ``True``.

        drivers (:obj:`bool`, optional):
            Include driver updates in the results. Default is ``False``

        summary (:obj:`bool`, optional):
            - ``True``: Return a summary of updates available for each category.
            - ``False`` (default): Return a detailed list of available updates.

            Default is ``False``.

        skip_installed (:obj:`bool`, optional):
            Skip installed updates in the results.

            Default is ``True``.

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

            Default is ``None``.

        severities (list):
            Specify the severities to include. Must be passed as a list. All
            severities returned by default.

            Severities include the following:

            * Critical
            * Important

            Default is ``None``.

        download (bool):
            (Overrides reporting functionality) Download the list of updates
            returned by this function. Run this function first with
            ``download=False`` to see what will be downloaded, then set
            ``download=True`` to download the updates.

            Default is ``False``.

        install (bool):
            (Overrides reporting functionality) Install the list of updates
            returned by this function. Run this function first with
            ``install=False`` to see what will be installed, then set
            ``install=True`` to install the updates.

            Default is ``False``.

        online (bool):
            Tells the Windows Update Agent go online to update its local update
            database. ``True`` will go online. ``False`` will use the local
            update database as is.

            Default is ``True``.

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
        salt '*' win_wua.list categories='["Critical Updates","Drivers"]'

        # List all Critical Security Updates
        salt '*' win_wua.list categories='["Security Updates"]' severities='["Critical"]'

        # List all updates with a severity of Critical
        salt '*' win_wua.list severities='["Critical"]'

        # A summary of all available updates
        salt '*' win_wua.list summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.list categories='["Feature Packs","Windows 8.1"]' summary=True
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

        summary (:obj:`bool`, optional):
            Return a summary instead of a detailed list of updates. ``True``
            will return a Summary, ``False`` will return a detailed list of
            installed updates.

            Default is ``False``.

        kbs_only (:obj:`bool`, optional):
            Only return a list of KBs installed on the system. If this parameter
            is passed, the ``summary`` parameter will be ignored.

            Default is ``False``.

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

        level (:obj:`int`, optional):
            Number from 1 to 4 indicating the update level:

            1. Never check for updates
            2. Check for updates but let me choose whether to download and
               install them
            3. Download updates but let me choose whether to install them
            4. Install updates automatically

            Default is ``None``.

        recommended (:obj:`bool`, optional):
            Boolean value that indicates whether to include optional or
            recommended updates when a search for updates and installation of
            updates is performed.

            Default is ``None``.

        featured (:obj:`bool`, optional):
            Boolean value that indicates whether to display notifications for
            featured updates.

            Default is ``None``.

        elevated (:obj:`bool`, optional):
            Boolean value that indicates whether non-administrators can perform
            some update-related actions without administrator approval.

            Default is ``None``.

        msupdate (:obj:`bool`, optional):
            Boolean value that indicates whether to turn on Microsoft Update for
            other Microsoft products.

            Default is ``None``.

        day (:obj:`str`, optional):
            Days of the week on which Automatic Updates installs or uninstalls
            updates. Accepted values:

            - Everyday
            - Monday
            - Tuesday
            - Wednesday
            - Thursday
            - Friday
            - Saturday

            Default is ``None``.

        time (:obj:`str`, optional):
            Time at which Automatic Updates installs or uninstalls updates. Must
            be in the ##:## 24hr format, eg. 3:00 PM would be 15:00. Must be in
            1 hour increments.

            Default is ``None``.

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


def _windir():
    """
    Return the current ``%WinDir%``. Computed on every call (rather than
    frozen as a module-level constant) so tests can sandbox it with
    ``monkeypatch.setenv("WINDIR", ...)``.
    """
    return os.environ.get("WINDIR", r"C:\Windows")


def _softwaredistribution_path():
    return os.path.join(_windir(), "SoftwareDistribution")


def _catroot2_path():
    return os.path.join(_windir(), "System32", "catroot2")


def _cbs_log_path():
    return os.path.join(_windir(), "Logs", "CBS", "CBS.log")


def _stop_wu_services():
    """
    Stop the Windows Update related services. Raises CommandExecutionError
    (without touching any files) if any service fails to stop.
    """
    ret = {}
    failed = []
    for svc in _WU_SERVICES:
        result = __salt__["service.stop"](svc)
        ret[svc] = result
        if not result:
            failed.append(svc)

    if failed:
        raise CommandExecutionError(
            "Failed to stop the following service(s), aborting reset: {}".format(
                ", ".join(failed)
            )
        )

    return ret


def _start_wu_services():
    """
    Start the Windows Update related services. Raises
    CommandExecutionError if any service fails to start.
    """
    ret = {}
    failed = []
    for svc in _WU_SERVICES:
        result = __salt__["service.start"](svc)
        ret[svc] = result
        if not result:
            failed.append(svc)

    if failed:
        raise CommandExecutionError(
            "Failed to start the following service(s) after reset: {}".format(
                ", ".join(failed)
            )
        )

    return ret


def _reset_dir(path, purge_old):
    """
    Rename ``path`` to ``path.old.<ms-timestamp>``, or delete it outright if
    ``purge_old`` is true. No-op (but not an error) if ``path`` doesn't
    exist.
    """
    ret = {"old_path": path, "new_path": None, "purged": False, "result": True}

    if not os.path.isdir(path):
        return ret

    if salt.utils.data.is_true(purge_old):
        try:
            shutil.rmtree(path)
        except OSError as exc:
            raise CommandExecutionError(f"Failed to remove '{path}': {exc}")
        ret["purged"] = True
        return ret

    new_path = f"{path}.old.{int(time.time() * 1000)}"
    while os.path.exists(new_path):
        new_path = f"{path}.old.{int(time.time() * 1000)}"

    try:
        os.rename(path, new_path)
    except OSError as exc:
        raise CommandExecutionError(f"Failed to rename '{path}' to '{new_path}': {exc}")

    ret["new_path"] = new_path
    return ret


def reset_datastore(purge_old=False):
    """
    .. versionadded:: 3009.0

    Resets the Windows Update datastore by stopping the Windows Update
    related services, renaming the ``SoftwareDistribution`` directory, and
    restarting the services. This is a common troubleshooting step for
    Windows Update issues, such as an update that reports success but does
    not persist (see the module-level note above for the full diagnostic
    workflow).

    .. warning::

        This stops the Windows Update related services (interrupting any
        in-progress download/install) and renames -- or, with
        ``purge_old=True``, permanently **deletes** -- the
        ``SoftwareDistribution`` directory, including all cached update
        payloads and the local update history/metadata. This is a
        destructive troubleshooting action and should not be run routinely
        or included in a default highstate. ``purge_old=True`` is
        irreversible: no ``.old.<timestamp>`` copy is left behind to
        recover from.

    Args:

        purge_old (bool, optional):
            If ``True``, deletes the existing ``SoftwareDistribution``
            directory instead of renaming it. This is irreversible.

            Default is ``False``

    Returns:

        dict: A dictionary containing the results of the reset

        .. code-block:: cfg

            {
                "reboot_pending": False,
                "SoftwareDistribution": {
                    "old_path": "C:\\Windows\\SoftwareDistribution",
                    "new_path": "C:\\Windows\\SoftwareDistribution.old.<ts>",
                    "purged": False,
                    "result": True,
                }
            }

    CLI Example:

    .. code-block:: bash

        salt '*' win_wua.reset_datastore
        salt '*' win_wua.reset_datastore purge_old=True
    """
    reboot_pending = salt.utils.win_update.needs_reboot()
    _stop_wu_services()
    try:
        result = _reset_dir(_softwaredistribution_path(), purge_old)
    finally:
        _start_wu_services()

    return {"reboot_pending": reboot_pending, "SoftwareDistribution": result}


def reset_catroot(purge_old=False):
    """
    .. versionadded:: 3009.0

    Resets the Windows Update catalog cache by stopping the Windows Update
    related services, renaming the ``catroot2`` directory, and restarting
    the services. This is a common troubleshooting step for Windows Update
    issues (see the module-level note above for the full diagnostic
    workflow).

    .. warning::

        This stops the Windows Update related services (interrupting any
        in-progress download/install) and renames -- or, with
        ``purge_old=True``, permanently **deletes** -- the ``catroot2``
        directory. This is a destructive troubleshooting action and should
        not be run routinely or included in a default highstate.
        ``purge_old=True`` is irreversible: no ``.old.<timestamp>`` copy is
        left behind to recover from.

    Args:

        purge_old (bool, optional):
            If ``True``, deletes the existing ``catroot2`` directory
            instead of renaming it. This is irreversible.

            Default is ``False``

    Returns:

        dict: A dictionary containing the results of the reset

        .. code-block:: cfg

            {
                "reboot_pending": False,
                "catroot2": {
                    "old_path": "C:\\Windows\\System32\\catroot2",
                    "new_path": "C:\\Windows\\System32\\catroot2.old.<ts>",
                    "purged": False,
                    "result": True,
                }
            }

    CLI Example:

    .. code-block:: bash

        salt '*' win_wua.reset_catroot
        salt '*' win_wua.reset_catroot purge_old=True
    """
    reboot_pending = salt.utils.win_update.needs_reboot()
    _stop_wu_services()
    try:
        result = _reset_dir(_catroot2_path(), purge_old)
    finally:
        _start_wu_services()

    return {"reboot_pending": reboot_pending, "catroot2": result}


def reset(purge_old=False):
    """
    .. versionadded:: 3009.0

    Convenience function that resets both the Windows Update datastore
    (``SoftwareDistribution``) and the Windows Update catalog cache
    (``catroot2``) in a single pass. This stops the Windows Update related
    services once, performs both resets, and restarts the services once,
    which is more efficient than calling
    :py:func:`win_wua.reset_datastore <salt.modules.win_wua.reset_datastore>`
    and :py:func:`win_wua.reset_catroot <salt.modules.win_wua.reset_catroot>`
    separately.

    .. warning::

        This stops the Windows Update related services (interrupting any
        in-progress download/install) and renames -- or, with
        ``purge_old=True``, permanently **deletes** -- both directories,
        including all cached update payloads and the local update
        history/metadata. This is a destructive troubleshooting action and
        should not be run routinely or included in a default highstate.
        ``purge_old=True`` is irreversible: no ``.old.<timestamp>`` copies
        are left behind to recover from.

    Args:

        purge_old (bool, optional):
            If ``True``, deletes the existing directories instead of
            renaming them. This is irreversible.

            Default is ``False``

    Returns:

        dict: A dictionary containing the results of both resets

        .. code-block:: cfg

            {
                "reboot_pending": False,
                "SoftwareDistribution": {
                    "old_path": "C:\\Windows\\SoftwareDistribution",
                    "new_path": "C:\\Windows\\SoftwareDistribution.old.<ts>",
                    "purged": False,
                    "result": True,
                },
                "catroot2": {
                    "old_path": "C:\\Windows\\System32\\catroot2",
                    "new_path": "C:\\Windows\\System32\\catroot2.old.<ts>",
                    "purged": False,
                    "result": True,
                },
            }

    CLI Example:

    .. code-block:: bash

        salt '*' win_wua.reset
        salt '*' win_wua.reset purge_old=True
    """
    reboot_pending = salt.utils.win_update.needs_reboot()
    _stop_wu_services()
    try:
        sd_result = _reset_dir(_softwaredistribution_path(), purge_old)
        catroot_result = _reset_dir(_catroot2_path(), purge_old)
    finally:
        _start_wu_services()

    return {
        "reboot_pending": reboot_pending,
        "SoftwareDistribution": sd_result,
        "catroot2": catroot_result,
    }


def _tail_lines(path, count):
    """
    Return the last ``count`` lines of ``path`` without reading the whole
    file into memory -- reads backward from EOF in chunks.
    """
    chunk_size = 65536
    with salt.utils.files.fopen(path, "rb") as fp_:
        fp_.seek(0, os.SEEK_END)
        remaining = fp_.tell()
        block = b""
        while remaining > 0 and block.count(b"\n") <= count:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            fp_.seek(remaining)
            block = fp_.read(read_size) + block

    text = block.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-count:])


def _grep_lines(path, patterns, max_matches=200, context=2):
    """
    Stream ``path`` line-by-line (no full in-memory read) and return only
    the lines matching any of ``patterns`` (plain substring match,
    case-insensitive), plus ``context`` lines before/after each match.
    Stops once ``max_matches`` matches have been found.
    """
    patterns_lower = [p.lower() for p in patterns]

    before_buffer = []
    after_remaining = 0
    last_emitted = -1
    result = []
    match_count = 0
    truncated = False

    with salt.utils.files.fopen(path, "r", encoding="utf-8", errors="replace") as fp_:
        for idx, raw_line in enumerate(fp_):
            line = raw_line.rstrip("\n")
            is_match = any(pattern in line.lower() for pattern in patterns_lower)

            if is_match:
                if match_count >= max_matches:
                    truncated = True
                    break
                match_count += 1

                for b_idx, b_line in before_buffer:
                    if b_idx > last_emitted:
                        result.append(b_line)
                        last_emitted = b_idx

                if idx > last_emitted:
                    result.append(line)
                    last_emitted = idx

                after_remaining = context
            elif after_remaining > 0:
                result.append(line)
                last_emitted = idx
                after_remaining -= 1

            before_buffer.append((idx, line))
            if len(before_buffer) > context:
                before_buffer.pop(0)

    text = "\n".join(result)
    if truncated:
        text += f"\n... (truncated: max_matches={max_matches} reached)"

    return text


def _tail_and_filter(path, tail=500, pattern=None, max_matches=200):
    """
    Shared implementation backing get_cbs_log/get_windows_update_log: read
    ``path``, applying either a ``pattern`` filter (whole-file scan,
    independent of ``tail``) or a ``tail`` limit (``None`` for the whole
    file).
    """
    if tail is not None and tail < 1:
        raise CommandExecutionError("'tail' must be a positive integer or None")

    if not os.path.isfile(path):
        raise CommandExecutionError(f"Log file not found: '{path}'")

    if pattern:
        # NOTE: this module defines its own module-level `list` function
        # (the win_wua.list CLI function, see `list()` above), which shadows
        # the builtin within this module's namespace -- use a comprehension
        # instead of `list(pattern)` here.
        patterns = [pattern] if isinstance(pattern, str) else [p for p in pattern]
        return _grep_lines(path, patterns, max_matches=max_matches)

    if tail is None:
        with salt.utils.files.fopen(
            path, "r", encoding="utf-8", errors="replace"
        ) as fp_:
            return fp_.read()

    return _tail_lines(path, tail)


def _write_out_file(out_file, content):
    out_dir = os.path.dirname(out_file)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    try:
        with salt.utils.files.fopen(out_file, "w", encoding="utf-8") as fp_:
            fp_.write(content)
    except OSError as exc:
        raise CommandExecutionError(f"Failed to write to '{out_file}': {exc}")


def get_cbs_log(tail=500, pattern=None, out_file=None, max_matches=200):
    """
    .. versionadded:: 3009.0

    Retrieves the contents of the Component-Based Servicing (CBS) log,
    located at ``%WinDir%\\Logs\\CBS\\CBS.log``. This log often contains
    detailed information about servicing/update failures not present in the
    Windows Update log -- see :py:func:`win_wua.get_windows_update_log
    <salt.modules.win_wua.get_windows_update_log>` for the complementary
    agent-level log; a full diagnosis usually needs both.

    .. note::

        Things worth searching for in the output: ``Failed``,
        ``Reject``/``rejected`` (a package the servicing stack refused to
        (re)apply), ``resolved as superseded`` / ``Resolved(...)`` state
        transitions, the specific package identifier
        (``Package_for_KB<number>~...``), and HRESULT-style codes
        (``0x800f...``, ``0x80073...``) which map to CBS/servicing-stack
        error codes -- a distinct range from the ``0x8024...`` WUA-specific
        codes seen in the Windows Update log. Searching for the KB number
        (``pattern="KB1234567"``) is usually the fastest way to find the
        relevant block in a huge log.

    .. warning::

        ``CBS.log`` can grow very large on long-lived systems. This
        function defaults to the last 500 lines to stay safe for return
        over the event bus. Passing ``tail=None`` reads the entire file
        into memory and returns it, which can be slow/large -- prefer
        ``pattern`` to search the whole file for specific terms instead.

    Args:

        tail (int, optional):
            If provided, only the last ``tail`` lines of the log are
            returned/written. Ignored when ``pattern`` is provided (which
            always scans the whole file).

            Default is ``500``. Pass ``None`` to return the entire log.

        pattern (str, list, optional):
            One or more plain substrings (case-insensitive) to search for.
            When provided, returns only matching lines plus a couple of
            context lines around each match, scanning the whole file
            regardless of ``tail``.

            Default is ``None``

        out_file (str, optional):
            If provided, the resulting (already tailed/filtered) content is
            also written to this path.

            Default is ``None``

        max_matches (int, optional):
            When ``pattern`` is used, the maximum number of matches to
            return.

            Default is ``200``

    Returns:

        str: The contents of the CBS log (or the last ``tail`` lines, or
        the lines matching ``pattern``)

    CLI Example:

    .. code-block:: bash

        salt '*' win_wua.get_cbs_log
        salt '*' win_wua.get_cbs_log tail=2000
        salt '*' win_wua.get_cbs_log pattern=KB5120233
        salt '*' win_wua.get_cbs_log pattern=KB5120233 out_file='C:\\temp\\cbs_kb.log'
    """
    content = _tail_and_filter(
        _cbs_log_path(), tail=tail, pattern=pattern, max_matches=max_matches
    )

    if out_file:
        _write_out_file(out_file, content)

    return content


def get_windows_update_log(tail=500, pattern=None, out_file=None, max_matches=200):
    """
    .. versionadded:: 3009.0

    Merges Windows Update ETW trace files into a single, readable
    ``WindowsUpdate.log`` file using the PowerShell ``Get-WindowsUpdateLog``
    cmdlet, then returns its contents -- see :py:func:`win_wua.get_cbs_log
    <salt.modules.win_wua.get_cbs_log>` for the complementary
    servicing-stack log; a full diagnosis usually needs both. The WU log
    shows the agent-level request/response, while the CBS log shows what
    the servicing stack actually did with it.

    .. note::

        Things worth searching for in the output: lines tagged
        ``FATAL``/``WARNING`` (log severity markers), ``COMAPI`` entries
        around the time of the install call (WUA-agent-level install/
        download phase transitions), WU-specific HRESULT codes
        (``0x8024...`` -- distinct from the ``0x800f...``/``0x80073...``
        CBS-range codes seen in :py:func:`win_wua.get_cbs_log
        <salt.modules.win_wua.get_cbs_log>`), and
        ``reportEventBatch``/install-phase-completion lines around reboot
        time.

    .. warning::

        This requires an elevated (Administrator) PowerShell session and is
        only available on Windows 8 / Server 2012 and later. Depending on
        the amount of Windows Update history on the system, this command
        can take several minutes to complete -- there is no internal
        timeout, so a caller needing one should apply it at the job level.
        The merged output can also be large; this function defaults to the
        last 500 lines for the same event-bus-size reasons as
        :py:func:`win_wua.get_cbs_log <salt.modules.win_wua.get_cbs_log>`.

    Args:

        tail (int, optional):
            If provided, only the last ``tail`` lines are returned. Ignored
            when ``pattern`` is provided.

            Default is ``500``. Pass ``None`` to return the entire log.

        pattern (str, list, optional):
            One or more plain substrings (case-insensitive) to search for,
            returning only matching lines plus a couple of context lines,
            scanning the whole file regardless of ``tail``.

            Default is ``None``

        out_file (str, optional):
            The path where the full merged log file should be written (used
            directly as the cmdlet's ``-LogPath``). The function's return
            value is still the tailed/filtered content, not the full file.

            Default is ``None``, which writes to a temporary location

        max_matches (int, optional):
            When ``pattern`` is used, the maximum number of matches to
            return.

            Default is ``200``

    Returns:

        str: The (tailed/filtered) contents of the merged Windows Update
        log

    CLI Example:

    .. code-block:: bash

        salt '*' win_wua.get_windows_update_log
        salt '*' win_wua.get_windows_update_log pattern=0x8024
        salt '*' win_wua.get_windows_update_log out_file='C:\\temp\\WindowsUpdate.log'
    """
    log_path = out_file or os.path.join(tempfile.gettempdir(), "WindowsUpdate.log")

    cmd = f"Get-WindowsUpdateLog -LogPath '{log_path}'"
    result = salt.utils.win_pwsh.run_dict(cmd)

    result_path = log_path
    if isinstance(result, dict) and result.get("Log"):
        result_path = result["Log"]

    if not os.path.isfile(result_path):
        raise CommandExecutionError(
            f"Get-WindowsUpdateLog did not produce a log file at '{result_path}'"
        )

    return _tail_and_filter(
        result_path, tail=tail, pattern=pattern, max_matches=max_matches
    )
