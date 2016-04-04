# -*- coding: utf-8 -*-
"""
Module for managing Windows Updates using the Windows Update Agent.

.. versionadded:: 2015.8.0

:depends:
        - win32com
        - pythoncom
"""
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=no-name-in-module,redefined-builtin

# Import 3rd-party libs
try:
    import win32com.client
    import pythoncom

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only works on Windows systems
    """
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return True
    return False


def _wua_search(skip_hidden=True,
                skip_installed=True,
                skip_present=False,
                skip_reboot=False,
                software_updates=True,
                driver_updates=True):
    # Build the search string
    search_string = ''
    search_params = []

    if skip_hidden:
        search_params.append('IsHidden=0')

    if skip_installed:
        search_params.append('IsInstalled=0')

    if skip_present:
        search_params.append('IsPresent=0')

    if skip_reboot:
        search_params.append('RebootRequired=0')

    for i in search_params:
        search_string += '{0} and '.format(i)

    if software_updates and driver_updates:
        search_string += 'Type=\'Software\' or Type=\'Driver\''
    elif software_updates:
        search_string += 'Type=\'Software\''
    elif driver_updates:
        search_string += 'Type=\'Driver\''
    else:
        log.debug('Neither Software nor Drivers included in search. Results will be empty.')
        return False

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create a session with the Windows Update Agent
    wua_session = win32com.client.Dispatch('Microsoft.Update.Session')

    # Create a searcher object
    wua_searcher = wua_session.CreateUpdateSearcher()

    # Search for updates
    try:
        log.debug('Searching for updates: {0}'.format(search_string))
        results = wua_searcher.Search(search_string)
        log.debug('Search completed successfully')
        return results.Updates
    except Exception as exc:
        log.info('Search for updates failed. {0}'.format(exc))
        return exc


def _filter_list_by_category(updates, categories=None):
    # This function filters the updates list based on Category

    if not updates:
        return 'No updates found'

    update_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

    for update in updates:

        category_match = False

        # If no categories were passed, return all categories
        # Set categoryMatch to True
        if categories is None:
            category_match = True
        else:
            # Loop through each category found in the update
            for category in update.Categories:
                # If the update category exists in the list of categories
                # passed, then set categoryMatch to True
                if category.Name in categories:
                    category_match = True

        if category_match:
            update_list.Add(update)

    return update_list


def _filter_list_by_severity(updates, severities=None):
    # This function filters the updates list based on Category

    if not updates:
        return 'No updates found'

    update_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

    for update in updates:

        severity_match = False

        # If no severities were passed, return all categories
        # Set severity_match to True
        if severities is None:
            severity_match = True
        else:
            # If the severity exists in the list of severities passed, then set
            # severity_match to True
            if update.MsrcSeverity in severities:
                severity_match = True

        if severity_match:
            update_list.Add(update)

    return update_list


def _list_updates_build_summary(updates):
    if updates.Count == 0:
        return 'Nothing to return'

    results = {}

    log.debug('Building update summary')

    # Build a dictionary containing a summary of updates available
    results['Total'] = 0
    results['Available'] = 0
    results['Downloaded'] = 0
    results['Installed'] = 0
    results['Categories'] = {}
    results['Severity'] = {}

    for update in updates:

        # Count the total number of updates available
        results['Total'] += 1

        # Updates available for download
        if not update.IsDownloaded and not update.IsInstalled:
            results['Available'] += 1

        # Updates downloaded awaiting install
        if update.IsDownloaded and not update.IsInstalled:
            results['Downloaded'] += 1

        # Updates installed
        if update.IsInstalled:
            results['Installed'] += 1

        # Add Categories and increment total for each one
        # The sum will be more than the total because each update can have
        # multiple categories
        for category in update.Categories:
            if category.Name in results['Categories']:
                results['Categories'][category.Name] += 1
            else:
                results['Categories'][category.Name] = 1

        # Add Severity Summary
        if update.MsrcSeverity:
            if update.MsrcSeverity in results['Severity']:
                results['Severity'][update.MsrcSeverity] += 1
            else:
                results['Severity'][update.MsrcSeverity] = 1

    return results


def _list_updates_build_report(updates):
    if updates.Count == 0:
        return 'Nothing to return'

    results = {}

    log.debug('Building a detailed report of the results.')

    # Build a dictionary containing details for each update

    for update in updates:

        guid = update.Identity.UpdateID
        results[guid] = {}
        results[guid]['guid'] = guid
        title = update.Title
        results[guid]['Title'] = title
        kb = ""
        if "KB" in title:
            kb = title[title.find("(") + 1: title.find(")")]
        results[guid]['KB'] = kb
        results[guid]['Description'] = update.Description
        results[guid]['Downloaded'] = str(update.IsDownloaded)
        results[guid]['Installed'] = str(update.IsInstalled)
        results[guid]['Mandatory'] = str(update.IsMandatory)
        results[guid]['UserInput'] = str(update.InstallationBehavior.CanRequestUserInput)
        results[guid]['EULAAccepted'] = str(update.EulaAccepted)

        # Severity of the Update
        # Can be: Critical, Important, Low, Moderate, <unspecified or empty>
        results[guid]['Severity'] = str(update.MsrcSeverity)

        # This value could easily be confused with the Reboot Behavior value
        # This is stating whether or not the INSTALLED update is awaiting
        # reboot
        results[guid]['NeedsReboot'] = str(update.RebootRequired)

        # Interpret the RebootBehavior value
        # This value is referencing an update that has NOT been installed
        rb = {0: 'Never Requires Reboot',
              1: 'Always Requires Reboot',
              2: 'Can Require Reboot'}
        results[guid]['RebootBehavior'] = rb[update.InstallationBehavior.RebootBehavior]

        # Add categories (nested list)
        results[guid]['Categories'] = []
        for category in update.Categories:
            results[guid]['Categories'].append(category.Name)

    return results


def list_update(name=None,
                download=False,
                install=False):
    """
    Returns details for all updates that match the search criteria

    :param str name:
        The name of the update you're searching for. This can be the GUID
        (preferred), a KB number, or the full name of the update. Run list_updates
        to get the GUID for the update you're looking for.

    :param bool download:
        Download the update returned by this function. Run this function first
        to see if the update exists, then set download=True to download the
        update.

    :param bool install:
        Install the update returned by this function. Run this function first
        to see if the update exists, then set install=True to install the
        update. This will override download=True

    :return:
        Returns a dict containing a list of updates that match the name if
        download and install are both set to False. Should usually be a single
        update, but can return multiple if a partial name is given. If download or
        install is set to true it will return the results of
        win_wua.download_updates:

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

    :return type: dict

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

    """
    if name is None:
        return 'Nothing to list'

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create a session with the Windows Update Agent
    wua_session = win32com.client.Dispatch('Microsoft.Update.Session')

    # Create the searcher
    wua_searcher = wua_session.CreateUpdateSearcher()

    # Create the found update collection
    wua_found = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

    # Try searching for the GUID first
    search_string = 'UpdateID=\'{0}\''.format(name)

    log.debug('Searching for update: {0}'.format(search_string.lower()))
    try:
        found_using_guid = False
        wua_search_result = wua_searcher.Search(search_string.lower())
        if wua_search_result.Updates.Count > 0:
            found_using_guid = True
        else:
            return "No update found"
    except Exception:
        log.debug('GUID not found, searching Title: {0}'.format(name))
        search_string = 'Type=\'Software\' or Type=\'Driver\''
        wua_search_result = wua_searcher.Search(search_string)

    # Populate wua_found
    if found_using_guid:
        # Found using GUID so there should only be one
        # Add it to the collection
        for update in wua_search_result.Updates:
            wua_found.Add(update)
    else:
        # Not found using GUID
        # Try searching the title for the Name or KB
        for update in wua_search_result.Updates:
            if name in update.Title:
                wua_found.Add(update)

    if install:
        guid_list = []
        for update in wua_found:
            guid_list.append(update.Identity.UpdateID)
        return install_updates(guid_list)

    if download:
        guid_list = []
        for update in wua_found:
            guid_list.append(update.Identity.UpdateID)
        return download_updates(guid_list)

    return _list_updates_build_report(wua_found)


def list_updates(software=True,
                 drivers=False,
                 summary=False,
                 installed=False,
                 categories=None,
                 severities=None,
                 download=False,
                 install=False):
    """
    Returns a detailed list of available updates or a summary

    :param bool software:
        Include software updates in the results (default is True)

    :param bool drivers:
        Include driver updates in the results (default is False)

    :param bool summary:
        True: Return a summary of updates available for each category.\
        False (default): Return a detailed list of available updates.

    :param bool installed:
        Include installed updates in the results (default if False)

    :param bool download:
        (Overrides reporting functionality) Download the list of updates
        returned by this function. Run this function first to see what will be
        installed, then set download=True to download the updates.

    :param bool install:
        (Overrides reporting functionality) Install the list of updates
        returned by this function. Run this function first to see what will be
        installed, then set install=True to install the updates. This will
        override download=True

    :param list categories:
        Specify the categories to list. Must be passed as a list. All
        categories returned by default.

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

    :param list severities:
        Specify the severities to include. Must be passed as a list. All
        severities returned by default.

        Severities include the following:

        * Critical
        * Important

    :return:
        Returns a dict containing either a summary or a list of updates:

        .. code-block:: cfg

            List of Updates:
            {'<GUID>': {'Title': <title>,
                        'KB': <KB>,
                        'GUID': <the globally uinique identifier for the update>
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
    :return type: dict

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

    """
    # Get the list of updates
    updates = _wua_search(software_updates=software,
                          driver_updates=drivers,
                          skip_installed=not installed)

    # Filter the list of updates
    updates = _filter_list_by_category(updates=updates,
                                       categories=categories)

    updates = _filter_list_by_severity(updates=updates,
                                       severities=severities)

    # If the list is empty after filtering, return a message
    if not updates:
        return 'No updates found. Check software and drivers parameters. One must be true.'

    if install:
        guid_list = []
        for update in updates:
            guid_list.append(update.Identity.UpdateID)
        return install_updates(guid_list)

    if download:
        guid_list = []
        for update in updates:
            guid_list.append(update.Identity.UpdateID)
        return download_updates(guid_list)

    if summary:
        return _list_updates_build_summary(updates)
    else:
        return _list_updates_build_report(updates)


def download_update(guid=None):
    """
    Downloads a single update

    :param guid: str
        A GUID for the update to be downloaded

    :return:
        A dictionary containing the status, a message, and a list of updates
        that were downloaded.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.download_update 12345678-abcd-1234-abcd-1234567890ab

    """
    return download_updates([guid])


def download_updates(guid=None):
    """
    Downloads updates that match the list of passed GUIDs. It's easier to use
    this function by using list_updates and setting install=True.

    :param guid:
        A list of GUIDs to be downloaded

    :return:
        A dictionary containing the status, a message, and a list of updates
        that were downloaded.

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.download_updates \
                guid=['12345678-abcd-1234-abcd-1234567890ab',\
                      '87654321-dcba-4321-dcba-ba0987654321']
    """
    # Check for empty GUID
    if guid is None:
        return "No GUID Specified"

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create a session with the Windows Update Agent
    wua_session = win32com.client.Dispatch('Microsoft.Update.Session')
    wua_session.ClientApplicationID = 'Salt: Install Update'

    # Create the Searcher, Downloader, Installer, and Collections
    wua_searcher = wua_session.CreateUpdateSearcher()
    wua_download_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
    wua_downloader = wua_session.CreateUpdateDownloader()

    ret = {}

    # Searching for the GUID
    search_string = ''
    search_list = ''
    log.debug('Searching for updates:')
    for ident in guid:
        log.debug('{0}'.format(ident))
        if search_string == '':
            search_string = 'UpdateID=\'{0}\''.format(ident.lower())
            search_list = '{0}'.format(ident.lower())
        else:
            search_string += ' or UpdateID=\'{0}\''.format(ident.lower())
            search_list += '\n{0}'.format(ident.lower())

    try:
        wua_search_result = wua_searcher.Search(search_string)
        if wua_search_result.Updates.Count == 0:
            log.debug('No Updates found for:\n\t\t{0}'.format(search_list))
            ret['Success'] = False
            ret['Details'] = 'No Updates found: {0}'.format(search_list)
            return ret
    except Exception:
        log.debug('Invalid Search String: {0}'.format(search_string))
        return 'Invalid Search String: {0}'.format(search_string)

    # List updates found
    log.debug('Found the following updates:')
    ret['Updates'] = {}
    for update in wua_search_result.Updates:
        # Check to see if the update is already installed
        ret['Updates'][update.Identity.UpdateID] = {}
        ret['Updates'][update.Identity.UpdateID]['Title'] = update.Title
        if update.IsInstalled:
            log.debug('Already Installed: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyInstalled'] = True
        # Make sure the EULA has been accepted
        if not update.EulaAccepted:
            log.debug('Accepting EULA: {0}'.format(update.Title))
            update.AcceptEula  # pylint: disable=W0104
        # Add to the list of updates that need to be downloaded
        if update.IsDownloaded:
            log.debug('Already Downloaded: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyDownloaded'] = True
        else:
            log.debug('To Be Downloaded: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyDownloaded'] = False
            wua_download_list.Add(update)

    # Check the download list
    if wua_download_list.Count == 0:
        # Not necessarily a failure, perhaps the update has been downloaded
        log.debug('No updates to download')
        ret['Success'] = False
        ret['Message'] = 'No updates to download'
        return ret

    # Download the updates
    log.debug('Downloading...')
    wua_downloader.Updates = wua_download_list

    try:
        result = wua_downloader.Download()

    except Exception as error:

        ret['Success'] = False
        ret['Result'] = format(error)

        hr, msg, exc, arg = error.args  # pylint: disable=W0633
        # Error codes found at the following site:
        # https://msdn.microsoft.com/en-us/library/windows/desktop/hh968413(v=vs.85).aspx
        fc = {-2145124316: 'No Updates: 0x80240024',
              -2145124284: 'Access Denied: 0x8024044'}
        try:
            failure_code = fc[exc[5]]
        except KeyError:
            failure_code = 'Unknown Failure: {0}'.format(error)

        log.debug('Download Failed: {0}'.format(failure_code))
        ret['error_msg'] = failure_code
        ret['location'] = 'Download Section of download_updates'
        ret['file'] = 'win_wua.py'

        return ret

    log.debug('Download Complete')

    rc = {0: 'Download Not Started',
          1: 'Download In Progress',
          2: 'Download Succeeded',
          3: 'Download Succeeded With Errors',
          4: 'Download Failed',
          5: 'Download Aborted'}
    log.debug(rc[result.ResultCode])

    if result.ResultCode in [2, 3]:
        ret['Success'] = True
    else:
        ret['Success'] = False

    ret['Message'] = rc[result.ResultCode]

    for i in range(wua_download_list.Count):
        uid = wua_download_list.Item(i).Identity.UpdateID
        ret['Updates'][uid]['Result'] = rc[result.GetUpdateResult(i).ResultCode]

    return ret


def install_update(guid=None):
    """
    Installs a single update

    :param guid: str
        A GUID for the update to be installed

    :return: dict
        A dictionary containing the details about the installed update

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.install_update 12345678-abcd-1234-abcd-1234567890ab

    """
    return install_updates([guid])


def install_updates(guid=None):
    """
    Installs updates that match the passed criteria. It may be easier to use the
    list_updates function and set install=True.

    :param guid: list
        A list of GUIDs to be installed

    :return: dict
        A dictionary containing the details about the installed updates

    CLI Examples:

    .. code-block:: bash

        # Normal Usage
        salt '*' win_wua.install_updates
         guid=['12345678-abcd-1234-abcd-1234567890ab',
         '87654321-dcba-4321-dcba-ba0987654321']
    """
    # Check for empty GUID
    if guid is None:
        return 'No GUID Specified'

    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create a session with the Windows Update Agent
    wua_session = win32com.client.Dispatch('Microsoft.Update.Session')
    wua_session.ClientApplicationID = 'Salt: Install Update'

    # Create the Searcher, Downloader, Installer, and Collections
    wua_searcher = wua_session.CreateUpdateSearcher()
    wua_download_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
    wua_downloader = wua_session.CreateUpdateDownloader()
    wua_install_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
    wua_installer = wua_session.CreateUpdateInstaller()

    ret = {}

    # Searching for the GUID
    search_string = ''
    search_list = ''
    log.debug('Searching for updates:')
    for ident in guid:
        log.debug('{0}'.format(ident))
        if search_string == '':
            search_string = 'UpdateID=\'{0}\''.format(ident.lower())
            search_list = '{0}'.format(ident.lower())
        else:
            search_string += ' or UpdateID=\'{0}\''.format(ident.lower())
            search_list += '\n{0}'.format(ident.lower())

    try:
        wua_search_result = wua_searcher.Search(search_string)
        if wua_search_result.Updates.Count == 0:
            log.debug('No Updates found for:\n\t\t{0}'.format(search_list))
            ret['Success'] = False
            ret['Details'] = 'No Updates found: {0}'.format(search_list)
            return ret
    except Exception:
        log.debug('Invalid Search String: {0}'.format(search_string))
        return 'Invalid Search String: {0}'.format(search_string)

    # List updates found
    log.debug('Found the following update:')
    ret['Updates'] = {}
    for update in wua_search_result.Updates:
        # Check to see if the update is already installed
        ret['Updates'][update.Identity.UpdateID] = {}
        ret['Updates'][update.Identity.UpdateID]['Title'] = update.Title
        if update.IsInstalled:
            log.debug('Already Installed: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyInstalled'] = True
        # Make sure the EULA has been accepted
        if not update.EulaAccepted:
            log.debug('Accepting EULA: {0}'.format(update.Title))
            update.AcceptEula  # pylint: disable=W0104
        # Add to the list of updates that need to be downloaded
        if update.IsDownloaded:
            log.debug('Already Downloaded: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyDownloaded'] = True
        else:
            log.debug('To Be Downloaded: {0}'.format(update.Identity.UpdateID))
            log.debug('\tTitle: {0}'.format(update.Title))
            ret['Updates'][update.Identity.UpdateID]['AlreadyDownloaded'] = False
            wua_download_list.Add(update)

    # Download the updates
    if wua_download_list.Count == 0:
        # Not necessarily a failure, perhaps the update has been downloaded
        # but not installed
        log.debug('No updates to download')
    else:
        # Otherwise, download the update
        log.debug('Downloading...')
        wua_downloader.Updates = wua_download_list

        try:
            wua_downloader.Download()
            log.debug('Download Complete')

        except Exception as error:

            ret['Success'] = False
            ret['Result'] = format(error)

            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            # Error codes found at the following site:
            # https://msdn.microsoft.com/en-us/library/windows/desktop/hh968413(v=vs.85).aspx
            fc = {-2145124316: 'No Updates: 0x80240024',
                  -2145124284: 'Access Denied: 0x8024044'}
            try:
                failure_code = fc[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.debug('Download Failed: {0}'.format(failure_code))
            ret['error_msg'] = failure_code
            ret['location'] = 'Download Section of install_updates'
            ret['file'] = 'win_wua.py'

            return ret

    # Install the updates
    for update in wua_search_result.Updates:
        # Make sure the update has actually been downloaded
        if update.IsDownloaded:
            log.debug('To be installed: {0}'.format(update.Title))
            wua_install_list.Add(update)

    if wua_install_list.Count == 0:
        # There are not updates to install
        # This would only happen if there was a problem with the download
        # If this happens often, perhaps some error checking for the download
        log.debug('No updates to install')
        ret['Success'] = False
        ret['Message'] = 'No Updates to install'
        return ret

    wua_installer.Updates = wua_install_list

    # Try to run the installer
    try:
        result = wua_installer.Install()

    except Exception as error:

        # See if we know the problem, if not return the full error
        ret['Success'] = False
        ret['Result'] = format(error)

        hr, msg, exc, arg = error.args  # pylint: disable=W0633
        # Error codes found at the following site:
        # https://msdn.microsoft.com/en-us/library/windows/desktop/hh968413(v=vs.85).aspx
        fc = {-2145124316: 'No Updates: 0x80240024',
              -2145124284: 'Access Denied: 0x8024044'}
        try:
            failure_code = fc[exc[5]]
        except KeyError:
            failure_code = 'Unknown Failure: {0}'.format(error)

        log.debug('Download Failed: {0}'.format(failure_code))
        ret['error_msg'] = failure_code
        ret['location'] = 'Install Section of install_updates'
        ret['file'] = 'win_wua.py'

        return ret

    rc = {0: 'Installation Not Started',
          1: 'Installation In Progress',
          2: 'Installation Succeeded',
          3: 'Installation Succeeded With Errors',
          4: 'Installation Failed',
          5: 'Installation Aborted'}
    log.debug(rc[result.ResultCode])

    if result.ResultCode in [2, 3]:
        ret['Success'] = True
        ret['NeedsReboot'] = result.RebootRequired
        log.debug('NeedsReboot: {0}'.format(result.RebootRequired))
    else:
        ret['Success'] = False

    ret['Message'] = rc[result.ResultCode]
    rb = {0: 'Never Reboot',
          1: 'Always Reboot',
          2: 'Poss Reboot'}
    for i in range(wua_install_list.Count):
        uid = wua_install_list.Item(i).Identity.UpdateID
        ret['Updates'][uid]['Result'] = rc[result.GetUpdateResult(i).ResultCode]
        ret['Updates'][uid]['RebootBehavior'] = rb[wua_install_list.Item(i).InstallationBehavior.RebootBehavior]

    return ret


def set_wu_settings(level=None,
                    recommended=None,
                    featured=None,
                    elevated=None,
                    msupdate=None,
                    day=None,
                    time=None):
    """
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

    :return:
    Returns a dictionary containing the results.

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.set_wu_settings level=4 recommended=True featured=False

    """
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
    """
    Get current Windows Update settings.

    :return:
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
    """
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
    """
    Check to see if Microsoft Update is Enabled
    Return Boolean
    """
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
    """
    Determines if the system needs to be rebooted.

    :return: bool
        True if the system requires a reboot, False if not

    CLI Examples:

    .. code-block:: bash

        salt '*' win_wua.get_needs_reboot

    """
    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create an AutoUpdate object
    obj_sys = win32com.client.Dispatch('Microsoft.Update.SystemInfo')

    if obj_sys.RebootRequired:
        return True
    else:
        return False
