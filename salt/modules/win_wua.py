# -*- coding: utf-8 -*-
'''
Module for managing Windows Updates using the Windows Update Agent.

.. versionadded:: 2015.8.0

:depends:
        - salt.utils.win_update
'''
# Import Python libs
from __future__ import absolute_import
import logging

# Import Salt libs
from salt.ext import six
import salt.utils
import salt.utils.win_update
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
try:
    import pythoncom
    import win32com.client
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems with PyWin32
    '''
    if not salt.utils.is_windows():
        return False, 'WUA: Only available on Window systems'

    if not HAS_PYWIN32:
        return False, 'WUA: Requires PyWin32 libraries'

    if not salt.utils.win_update.HAS_PYWIN32:
        return False, 'WUA: Missing Libraries required by salt.utils.win_update'

    return True


def available(software=True,
              drivers=True,
              summary=False,
              skip_installed=True,
              skip_hidden=True,
              skip_mandatory=False,
              skip_reboot=False,
              categories=None,
              severities=None,
              ):
    '''
    .. versionadded:: Nitrogen

    List updates that match the passed criteria.

    Args:

        software (bool): Include software updates in the results (default is
        True)

        drivers (bool): Include driver updates in the results (default is False)

        summary (bool):
        - True: Return a summary of updates available for each category.
        - False (default): Return a detailed list of available updates.

        skip_installed (bool): Skip updates that are already installed. Default
        is False.

        skip_hidden (bool): Skip updates that have been hidden. Default is True.

        skip_mandatory (bool): Skip mandatory updates. Default is False.

        skip_reboot (bool): Skip updates that require a reboot. Default is
        False.

        categories (list): Specify the categories to list. Must be passed as a
        list. All categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set drivers=True)
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

        severities (list): Specify the severities to include. Must be passed as
        a list. All severities returned by default.

            Severities include the following:

            * Critical
            * Important

    Returns:

        dict: Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally unique identifier for the update>
                        'Description': <description>,
                        'Downloaded': <has the update been downloaded>,
                        'Installed': <has the update been installed>,
                        'Mandatory': <is the update mandatory>,
                        'UserInput': <is user input required>,
                        'EULAAccepted': <has the EULA been accepted>,
                        'Severity': <update severity>,
                        'NeedsReboot': <is the update installed and awaiting reboot>,
                        'RebootBehavior': <will the update require a reboot>,
                        'Categories': [ '<category 1>',
                                        '<category 2>',
                                        ...]
                        }
            }

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': { <category 1>: <total for that category>,
                             <category 2>: <total for category 2>,
                             ... }
            }

    CLI Examples:

    .. code-block:: bash

        # Normal Usage (list all software updates)
        salt '*' win_wua.available

        # List all updates with categories of Critical Updates and Drivers
        salt '*' win_wua.available categories=['Critical Updates','Drivers']

        # List all Critical Security Updates
        salt '*' win_wua.available categories=['Security Updates'] severities=['Critical']

        # List all updates with a severity of Critical
        salt '*' win_wua.available severities=['Critical']

        # A summary of all available updates
        salt '*' win_wua.available summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.available categories=['Feature Packs','Windows 8.1'] summary=True
    '''

    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Look for available
    updates = wua.available(skip_hidden, skip_installed, skip_mandatory,
                            skip_reboot, software, drivers, categories,
                            severities)

    # Return results as Summary or Details
    return updates.summary() if summary else updates.list()


def list_update(name, download=False, install=False):
    '''
    .. deprecated:: Nitrogen
       Use :func:`get` instead
    Returns details for all updates that match the search criteria

    Args:
        name (str): The name of the update you're searching for. This can be the
        GUID, a KB number, or any part of the name of the update. GUIDs and
        KBs are preferred. Run ``list_updates`` to get the GUID for the update
        you're looking for.

        download (bool): Download the update returned by this function. Run this
        function first to see if the update exists, then set ``download=True``
        to download the update.

        install (bool): Install the update returned by this function. Run this
        function first to see if the update exists, then set ``install=True`` to
        install the update.

    Returns:
        dict: Returns a dict containing a list of updates that match the name if
        download and install are both set to False. Should usually be a single
        update, but can return multiple if a partial name is given.

        If download or install is set to true it will return the results of the
        operation.

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally unique identifier for the update>
                        'Description': <description>,
                        'Downloaded': <has the update been downloaded>,
                        'Installed': <has the update been installed>,
                        'Mandatory': <is the update mandatory>,
                        'UserInput': <is user input required>,
                        'EULAAccepted': <has the EULA been accepted>,
                        'Severity': <update severity>,
                        'NeedsReboot': <is the update installed and awaiting reboot>,
                        'RebootBehavior': <will the update require a reboot>,
                        'Categories': [ '<category 1>',
                                        '<category 2>',
                                        ...]
                        }
            }

    CLI Examples:

    .. code-block:: bash

        # Recommended Usage using GUID without braces
        # Use this to find the status of a specific update
        salt '*' win_wua.list_update 12345678-abcd-1234-abcd-1234567890ab

        # Use the following if you don't know the GUID:

        # Using a KB number (could possibly return multiple results)
        # Not all updates have an associated KB
        salt '*' win_wua.list_update KB3030298

        # Using part or all of the name of the update
        # Could possibly return multiple results
        # Not all updates have an associated KB
        salt '*' win_wua.list_update 'Microsoft Camera Codec Pack'
    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'get\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return get(name, download, install)


def get(name, download=False, install=False):
    '''
    .. versionadded:: Nitrogen

    Returns details for all updates that match the search criteria

    Args:
        name (str): The name of the update you're searching for. This can be the
        GUID, a KB number, or any part of the name of the update. GUIDs and
        KBs are preferred. Run ``list`` to get the GUID for the update
        you're looking for.

        download (bool): Download the update returned by this function. Run this
        function first to see if the update exists, then set ``download=True``
        to download the update.

        install (bool): Install the update returned by this function. Run this
        function first to see if the update exists, then set ``install=True`` to
        install the update.

    Returns:
        dict: Returns a dict containing a list of updates that match the name if
        download and install are both set to False. Should usually be a single
        update, but can return multiple if a partial name is given.

        If download or install is set to true it will return the results of the
        operation.

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally unique identifier for the update>
                        'Description': <description>,
                        'Downloaded': <has the update been downloaded>,
                        'Installed': <has the update been installed>,
                        'Mandatory': <is the update mandatory>,
                        'UserInput': <is user input required>,
                        'EULAAccepted': <has the EULA been accepted>,
                        'Severity': <update severity>,
                        'NeedsReboot': <is the update installed and awaiting reboot>,
                        'RebootBehavior': <will the update require a reboot>,
                        'Categories': [ '<category 1>',
                                        '<category 2>',
                                        ...]
                        }
            }

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
    '''
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Update
    updates = wua.search(name)

    ret = {}

    # Download
    if download or install:
        ret['Download'] = wua.download(updates)

    # Install
    if install:
        ret['Install'] = wua.install(updates)

    return ret if ret else updates.list()


def list_updates(software=True,
                 drivers=False,
                 summary=False,
                 skip_installed=True,
                 categories=None,
                 severities=None,
                 download=False,
                 install=False):
    '''
    .. deprecated:: Nitrogen
       Use :func:`list` instead

    Returns a detailed list of available updates or a summary. If download or
    install is True the same list will be downloaded and/or installed.

    Args:
        software (bool): Include software updates in the results (default is
        True)

        drivers (bool): Include driver updates in the results (default is False)

        summary (bool):
        - True: Return a summary of updates available for each category.
        - False (default): Return a detailed list of available updates.

        skip_installed (bool): Skip installed updates in the results (default is
        False)

        download (bool): (Overrides reporting functionality) Download the list
        of updates returned by this function. Run this function first with
        ``download=False`` to see what will be downloaded, then set
        ``download=True`` to download the updates.

        install (bool): (Overrides reporting functionality) Install the list of
        updates returned by this function. Run this function first with
        ``install=False`` to see what will be installed, then set
        ``install=True`` to install the updates.

        categories (list): Specify the categories to list. Must be passed as a
        list. All categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set drivers=True)
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

        severities (list): Specify the severities to include. Must be passed as
        a list. All severities returned by default.

            Severities include the following:

            * Critical
            * Important

    Returns:

        dict: Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally unique identifier for the update>
                        'Description': <description>,
                        'Downloaded': <has the update been downloaded>,
                        'Installed': <has the update been installed>,
                        'Mandatory': <is the update mandatory>,
                        'UserInput': <is user input required>,
                        'EULAAccepted': <has the EULA been accepted>,
                        'Severity': <update severity>,
                        'NeedsReboot': <is the update installed and awaiting reboot>,
                        'RebootBehavior': <will the update require a reboot>,
                        'Categories': [ '<category 1>',
                                        '<category 2>',
                                        ...]
                        }
            }

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': { <category 1>: <total for that category>,
                             <category 2>: <total for category 2>,
                             ... }
            }

    CLI Examples:

    .. code-block:: bash

        # Normal Usage (list all software updates)
        salt '*' win_wua.list_updates

        # List all updates with categories of Critical Updates and Drivers
        salt '*' win_wua.list_updates categories=['Critical Updates','Drivers']

        # List all Critical Security Updates
        salt '*' win_wua.list_updates categories=['Security Updates'] severities=['Critical']

        # List all updates with a severity of Critical
        salt '*' win_wua.list_updates severities=['Critical']

        # A summary of all available updates
        salt '*' win_wua.list_updates summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.list_updates categories=['Feature Packs','Windows 8.1'] summary=True
    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'list\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return list(software, drivers, summary, skip_installed, categories,
                severities, download, install)


def list(software=True,
         drivers=False,
         summary=False,
         skip_installed=True,
         categories=None,
         severities=None,
         download=False,
         install=False):
    '''
    .. versionadded:: Nitrogen

    Returns a detailed list of available updates or a summary. If download or
    install is True the same list will be downloaded and/or installed.

    Args:
        software (bool): Include software updates in the results (default is
        True)

        drivers (bool): Include driver updates in the results (default is False)

        summary (bool):
        - True: Return a summary of updates available for each category.
        - False (default): Return a detailed list of available updates.

        skip_installed (bool): Skip installed updates in the results (default is
        False)

        download (bool): (Overrides reporting functionality) Download the list
        of updates returned by this function. Run this function first with
        ``download=False`` to see what will be downloaded, then set
        ``download=True`` to download the updates.

        install (bool): (Overrides reporting functionality) Install the list of
        updates returned by this function. Run this function first with
        ``install=False`` to see what will be installed, then set
        ``install=True`` to install the updates.

        categories (list): Specify the categories to list. Must be passed as a
        list. All categories returned by default.

            Categories include the following:

            * Critical Updates
            * Definition Updates
            * Drivers (make sure you set drivers=True)
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

        severities (list): Specify the severities to include. Must be passed as
        a list. All severities returned by default.

            Severities include the following:

            * Critical
            * Important

    Returns:

        dict: Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally unique identifier for the update>
                        'Description': <description>,
                        'Downloaded': <has the update been downloaded>,
                        'Installed': <has the update been installed>,
                        'Mandatory': <is the update mandatory>,
                        'UserInput': <is user input required>,
                        'EULAAccepted': <has the EULA been accepted>,
                        'Severity': <update severity>,
                        'NeedsReboot': <is the update installed and awaiting reboot>,
                        'RebootBehavior': <will the update require a reboot>,
                        'Categories': [ '<category 1>',
                                        '<category 2>',
                                        ...]
                        }
            }

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': { <category 1>: <total for that category>,
                             <category 2>: <total for category 2>,
                             ... }
            }

    CLI Examples:

    .. code-block:: bash

        # Normal Usage (list all software updates)
        salt '*' win_wua.list_updates

        # List all updates with categories of Critical Updates and Drivers
        salt '*' win_wua.list_updates categories=['Critical Updates','Drivers']

        # List all Critical Security Updates
        salt '*' win_wua.list_updates categories=['Security Updates'] severities=['Critical']

        # List all updates with a severity of Critical
        salt '*' win_wua.list_updates severities=['Critical']

        # A summary of all available updates
        salt '*' win_wua.list_updates summary=True

        # A summary of all Feature Packs and Windows 8.1 Updates
        salt '*' win_wua.list_updates categories=['Feature Packs','Windows 8.1'] summary=True
    '''
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Update
    updates = wua.available(skip_installed=skip_installed, software=software,
                            drivers=drivers, categories=categories,
                            severities=severities)

    ret = {}

    # Download
    if download or install:
        ret['Download'] = wua.download(updates.updates)

    # Install
    if install:
        ret['Install'] = wua.install(updates.updates)

    if not ret:
        return updates.summary() if summary else updates.list()

    return ret


def download_update(name):
    '''
    .. deprecated:: Nitrogen
       Use :func:`download` instead

    Downloads a single update.

    Args:

        name (str): The name of the update to download. This can be a GUID, a KB
        number, or any part of the name. To ensure a single item is matched the
        GUID is preferred.

        .. note:: If more than one result is returned an error will be raised.

    Returns:
        dict: A dictionary containing the results of the download

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.download_update 12345678-abcd-1234-abcd-1234567890ab

        salt '*' win_wua.download_update KB12312321

    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'download\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return download(name)


def download_updates(names):
    '''
    .. deprecated:: Nitrogen
       Use :func:`download` instead

    Downloads updates that match the list of passed identifiers. It's easier to
    use this function by using list_updates and setting install=True.

    Args:

        names (list): A list of updates to download. This can be any combination
        of GUIDs, KB numbers, or names. GUIDs or KBs are preferred.

    Returns:

        dict: A dictionary containing the details about the downloaded updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.download guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB2131233']
    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'download\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return download(names)


def download(names):
    '''
    .. versionadded:: Nitrogen

    Downloads updates that match the list of passed identifiers. It's easier to
    use this function by using list_updates and setting install=True.

    Args:

        names (str, list): A single update or a list of updates to download.
        This can be any combination of GUIDs, KB numbers, or names. GUIDs or KBs
        are preferred.

    Returns:

        dict: A dictionary containing the details about the downloaded updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.download guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB2131233']
    '''
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Update
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError('No updates found')

    if updates.count() > len(names):
        raise CommandExecutionError('Multiple updates found, names need to be '
                                    'more specific')

    return wua.download(updates)


def install_update(name):
    '''
    .. deprecated:: Nitrogen
       Use :func:`install` instead

    Installs a single update

    Args:

        name (str): The name of the update to install. This can be a GUID, a KB
        number, or any part of the name. To ensure a single item is matched the
        GUID is preferred.

        .. note:: If no results or more than one result is returned an error
           will be raised.

    Returns:
        dict: A dictionary containing the results of the install

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.install_update 12345678-abcd-1234-abcd-1234567890ab

        salt '*' win_wua.install_update KB12312231
    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'install\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return install(name)


def install_updates(names):
    '''
    .. deprecated:: Nitrogen
       Use :func:`install` instead

    Installs updates that match the list of identifiers. It may be easier to use
    the list_updates function and set install=True.

    Args:

        names (list): A list of updates to install. This can be any combination
        of GUIDs, KB numbers, or names. GUIDs or KBs are preferred.

    Returns:

        dict: A dictionary containing the details about the installed updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.install_updates guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB12323211']
    '''
    salt.utils.warn_until(
        'Fluorine',
        'This function is replaced by \'install\' as of Salt Nitrogen. This'
        'warning will be removed in Salt Fluorine.')
    return install(names)


def install(names):
    '''
    .. versionadded:: Nitrogen

    Installs updates that match the list of identifiers. It may be easier to use
    the list_updates function and set install=True.

    Args:

        names (str, list): A single update or a list of updates to install.
        This can be any combination of GUIDs, KB numbers, or names. GUIDs or KBs
        are preferred.

    Returns:

        dict: A dictionary containing the details about the installed updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.install_updates guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB12323211']
    '''
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Updates
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError('No updates found')

    if updates.count() > len(names):
        raise CommandExecutionError('Multiple updates found, names need to be '
                                    'more specific')

    return wua.install(updates)


def uninstall(names):
    '''
    .. versionadded:: Nitrogen

    Uninstall updates.

    Args:

        names (str, list): A single update or a list of updates to uninstall.
        This can be any combination of GUIDs, KB numbers, or names. GUIDs or KBs
        are preferred.

    Returns:

        dict: A dictionary containing the details about the uninstalled updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.uninstall KB3121212

        # As a list
        salt '*' win_wua.uninstall guid=['12345678-abcd-1234-abcd-1234567890ab', 'KB1231231']
    '''
    # Create a Windows Update Agent instance
    wua = salt.utils.win_update.WindowsUpdateAgent()

    # Search for Updates
    updates = wua.search(names)

    if updates.count() == 0:
        raise CommandExecutionError('No updates found')

    return wua.uninstall(updates)


def set_wu_settings(level=None,
                    recommended=None,
                    featured=None,
                    elevated=None,
                    msupdate=None,
                    day=None,
                    time=None):
    '''
    Change Windows Update settings. If no parameters are passed, the current
    value will be returned.

    :param int level:
        Number from 1 to 4 indicating the update level:
            1. Never check for updates
            2. Check for updates but let me choose whether to download and install them
            3. Download updates but let me choose whether to install them
            4. Install updates automatically
    :param bool recommended:
        Boolean value that indicates whether to include optional or recommended
        updates when a search for updates and installation of updates is
        performed.

    :param bool featured:
        Boolean value that indicates whether to display notifications for
        featured updates.

    :param bool elevated:
        Boolean value that indicates whether non-administrators can perform some
        update-related actions without administrator approval.

    :param bool msupdate:
        Boolean value that indicates whether to turn on Microsoft Update for
        other Microsoft products

    :param str day:
        Days of the week on which Automatic Updates installs or uninstalls
        updates.
        Accepted values:
            - Everyday
            - Monday
            - Tuesday
            - Wednesday
            - Thursday
            - Friday
            - Saturday

    :param str time:
        Time at which Automatic Updates installs or uninstalls updates. Must be
        in the ##:## 24hr format, eg. 3:00 PM would be 15:00

    :return: Returns a dictionary containing the results.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.set_wu_settings level=4 recommended=True featured=False

    '''
    ret = {}
    ret['Success'] = True

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create an AutoUpdate object
    obj_au = win32com.client.Dispatch('Microsoft.Update.AutoUpdate')

    # Create an AutoUpdate Settings Object
    obj_au_settings = obj_au.Settings

    # Only change the setting if it's passed
    if level is not None:
        obj_au_settings.NotificationLevel = int(level)
        result = obj_au_settings.Save()
        if result is None:
            ret['Level'] = level
        else:
            ret['Comment'] = "Settings failed to save. Check permissions."
            ret['Success'] = False

    if recommended is not None:
        obj_au_settings.IncludeRecommendedUpdates = recommended
        result = obj_au_settings.Save()
        if result is None:
            ret['Recommended'] = recommended
        else:
            ret['Comment'] = "Settings failed to save. Check permissions."
            ret['Success'] = False

    if featured is not None:
        obj_au_settings.FeaturedUpdatesEnabled = featured
        result = obj_au_settings.Save()
        if result is None:
            ret['Featured'] = featured
        else:
            ret['Comment'] = "Settings failed to save. Check permissions."
            ret['Success'] = False

    if elevated is not None:
        obj_au_settings.NonAdministratorsElevated = elevated
        result = obj_au_settings.Save()
        if result is None:
            ret['Elevated'] = elevated
        else:
            ret['Comment'] = "Settings failed to save. Check permissions."
            ret['Success'] = False

    if day is not None:
        # Check that day is valid
        days = {'Everyday': 0,
                'Sunday': 1,
                'Monday': 2,
                'Tuesday': 3,
                'Wednesday': 4,
                'Thursday': 5,
                'Friday': 6,
                'Saturday': 7}
        if day not in days:
            ret['Comment'] = "Day needs to be one of the following: Everyday," \
                             "Monday, Tuesday, Wednesday, Thursday, Friday, " \
                             "Saturday"
            ret['Success'] = False
        else:
            # Set the numeric equivalent for the day setting
            obj_au_settings.ScheduledInstallationDay = days[day]
            result = obj_au_settings.Save()
            if result is None:
                ret['Day'] = day
            else:
                ret['Comment'] = "Settings failed to save. Check permissions."
                ret['Success'] = False

    if time is not None:
        # Check for time as a string: if the time is not quoted, yaml will
        # treat it as an integer
        if not isinstance(time, six.string_types):
            ret['Comment'] = "Time argument needs to be a string; it may need to"\
                             "be quoted. Passed {0}. Time not set.".format(time)
            ret['Success'] = False
        # Check for colon in the time
        elif ':' not in time:
            ret['Comment'] = "Time argument needs to be in 00:00 format." \
                             " Passed {0}. Time not set.".format(time)
            ret['Success'] = False
        else:
            # Split the time by :
            t = time.split(":")
            # We only need the hours value
            obj_au_settings.FeaturedUpdatesEnabled = t[0]
            result = obj_au_settings.Save()
            if result is None:
                ret['Time'] = time
            else:
                ret['Comment'] = "Settings failed to save. Check permissions."
                ret['Success'] = False

    if msupdate is not None:
        # Microsoft Update requires special handling
        # First load the MS Update Service Manager
        obj_sm = win32com.client.Dispatch('Microsoft.Update.ServiceManager')

        # Give it a bogus name
        obj_sm.ClientApplicationID = "My App"

        if msupdate:
            # msupdate is true, so add it to the services
            try:
                obj_sm.AddService2('7971f918-a847-4430-9279-4a52d1efe18d', 7, '')
                ret['msupdate'] = msupdate
            except Exception as error:
                hr, msg, exc, arg = error.args  # pylint: disable=W0633
                # Consider checking for -2147024891 (0x80070005) Access Denied
                ret['Comment'] = "Failed with failure code: {0}".format(exc[5])
                ret['Success'] = False
        else:
            # msupdate is false, so remove it from the services
            # check to see if the update is there or the RemoveService function
            # will fail
            if _get_msupdate_status():
                # Service found, remove the service
                try:
                    obj_sm.RemoveService('7971f918-a847-4430-9279-4a52d1efe18d')
                    ret['msupdate'] = msupdate
                except Exception as error:
                    hr, msg, exc, arg = error.args  # pylint: disable=W0633
                    # Consider checking for the following
                    # -2147024891 (0x80070005) Access Denied
                    # -2145091564 (0x80248014) Service Not Found (shouldn't get
                    # this with the check for _get_msupdate_status above
                    ret['Comment'] = "Failed with failure code: {0}".format(exc[5])
                    ret['Success'] = False
            else:
                ret['msupdate'] = msupdate

    ret['Reboot'] = get_needs_reboot()

    return ret


def get_wu_settings():
    '''
    Get current Windows Update settings.

    Returns:

        dict: A dictionary of Windows Update settings:

        Featured Updates:
            Boolean value that indicates whether to display notifications for
            featured updates.
        Group Policy Required (Read-only):
            Boolean value that indicates whether Group Policy requires the Automatic
            Updates service.
        Microsoft Update:
            Boolean value that indicates whether to turn on Microsoft Update for
            other Microsoft Products
        Needs Reboot:
            Boolean value that indicates whether the machine is in a reboot pending
            state.
        Non Admins Elevated:
            Boolean value that indicates whether non-administrators can perform some
            update-related actions without administrator approval.
        Notification Level:
            Number 1 to 4 indicating the update level:
                1. Never check for updates
                2. Check for updates but let me choose whether to download and install them
                3. Download updates but let me choose whether to install them
                4. Install updates automatically
        Read Only (Read-only):
            Boolean value that indicates whether the Automatic Update
            settings are read-only.
        Recommended Updates:
            Boolean value that indicates whether to include optional or recommended
            updates when a search for updates and installation of updates is
            performed.
        Scheduled Day:
            Days of the week on which Automatic Updates installs or uninstalls
            updates.
        Scheduled Time:
            Time at which Automatic Updates installs or uninstalls updates.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.get_wu_settings
    '''
    ret = {}

    day = ['Every Day',
           'Sunday',
           'Monday',
           'Tuesday',
           'Wednesday',
           'Thursday',
           'Friday',
           'Saturday']

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create an AutoUpdate object
    obj_au = win32com.client.Dispatch('Microsoft.Update.AutoUpdate')

    # Create an AutoUpdate Settings Object
    obj_au_settings = obj_au.Settings

    # Populate the return dictionary
    ret['Featured Updates'] = obj_au_settings.FeaturedUpdatesEnabled
    ret['Group Policy Required'] = obj_au_settings.Required
    ret['Microsoft Update'] = _get_msupdate_status()
    ret['Needs Reboot'] = get_needs_reboot()
    ret['Non Admins Elevated'] = obj_au_settings.NonAdministratorsElevated
    ret['Notification Level'] = obj_au_settings.NotificationLevel
    ret['Read Only'] = obj_au_settings.ReadOnly
    ret['Recommended Updates'] = obj_au_settings.IncludeRecommendedUpdates
    ret['Scheduled Day'] = day[obj_au_settings.ScheduledInstallationDay]
    # Scheduled Installation Time requires special handling to return the time
    # in the right format
    if obj_au_settings.ScheduledInstallationTime < 10:
        ret['Scheduled Time'] = '0{0}:00'.\
            format(obj_au_settings.ScheduledInstallationTime)
    else:
        ret['Scheduled Time'] = '{0}:00'.\
            format(obj_au_settings.ScheduledInstallationTime)

    return ret


def _get_msupdate_status():
    '''
    Check to see if Microsoft Update is Enabled
    Return Boolean
    '''
    # To get the status of Microsoft Update we actually have to check the
    # Microsoft Update Service Manager
    # Create a ServiceManager Object
    obj_sm = win32com.client.Dispatch('Microsoft.Update.ServiceManager')

    # Return a collection of loaded Services
    col_services = obj_sm.Services

    # Loop through the collection to find the Microsoft Udpate Service
    # If it exists return True otherwise False
    for service in col_services:
        if service.name == 'Microsoft Update':
            return True

    return False


def get_needs_reboot():
    '''
    Determines if the system needs to be rebooted.

    Returns:

        bool: True if the system requires a reboot, False if not

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.get_needs_reboot

    '''
    return salt.utils.win_update.needs_reboot()
