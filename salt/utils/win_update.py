# -*- coding: utf-8 -*-
'''
Classes for working with Windows Update Agent
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import subprocess

# Import Salt libs
import salt.utils.args
import salt.utils.data
from salt.ext import six
from salt.ext.six.moves import range
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
try:
    import win32com.client
    import pythoncom
    import pywintypes
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

log = logging.getLogger(__name__)


class Updates(object):
    '''
    Wrapper around the 'Microsoft.Update.UpdateColl' instance
    Adds the list and summary functions. For use by the WindowUpdateAgent class.

    Usage:
    .. code-block:: python

        # Create an instance
        updates = Updates()

        # Bind to the collection object
        found = updates.updates

        # This exposes Collections properties and methods
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386107(v=vs.85).aspx
        found.Count
        found.Add

        # To use custom functions, use the original instance
        # Return the number of updates inside the collection
        updates.count()

        # Return a list of updates in the collection and details in a dictionary
        updates.list()

        # Return a summary of the contents of the updates collection
        updates.summary()
    '''

    update_types = {1: 'Software',
                    2: 'Driver'}

    reboot_behavior = {0: 'Never Requires Reboot',
                       1: 'Always Requires Reboot',
                       2: 'Can Require Reboot'}

    def __init__(self):
        '''
        Initialize the updates collection. Can be accessed via
        ``Updates.updates``
        '''
        self.updates = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

    def count(self):
        '''
        Return how many records are in the Microsoft Update Collection

        Returns:
            int: The number of updates in the collection

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            updates = salt.utils.win_update.Updates()
            updates.count()
        '''
        return self.updates.Count

    def list(self):
        '''
        Create a dictionary with the details for the updates in the collection.

        Returns:
            dict: Details about each update

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

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            updates = salt.utils.win_update.Updates()
            updates.list()
        '''
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386099(v=vs.85).aspx
        if self.count() == 0:
            return 'Nothing to return'

        log.debug('Building a detailed report of the results.')

        # Build a dictionary containing details for each update
        results = {}
        for update in self.updates:

            results[update.Identity.UpdateID] = {
                'guid': update.Identity.UpdateID,
                'Title': six.text_type(update.Title),
                'Type': self.update_types[update.Type],
                'Description': update.Description,
                'Downloaded': bool(update.IsDownloaded),
                'Installed': bool(update.IsInstalled),
                'Mandatory': bool(update.IsMandatory),
                'EULAAccepted': bool(update.EulaAccepted),
                'NeedsReboot': bool(update.RebootRequired),
                'Severity': six.text_type(update.MsrcSeverity),
                'UserInput':
                    bool(update.InstallationBehavior.CanRequestUserInput),
                'RebootBehavior':
                    self.reboot_behavior[
                        update.InstallationBehavior.RebootBehavior],
                'KBs': ['KB' + item for item in update.KBArticleIDs],
                'Categories': [item.Name for item in update.Categories]
            }

        return results

    def summary(self):
        '''
        Create a dictionary with a summary of the updates in the collection.

        Returns:
            dict: Summary of the contents of the collection

        .. code-block:: cfg

            Summary of Updates:
            {'Total': <total number of updates returned>,
             'Available': <updates that are not downloaded or installed>,
             'Downloaded': <updates that are downloaded but not installed>,
             'Installed': <updates installed (usually 0 unless installed=True)>,
             'Categories': { <category 1>: <total for that category>,
                             <category 2>: <total for category 2>,
                             ... }
            }
        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            updates = salt.utils.win_update.Updates()
            updates.summary()
        '''
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386099(v=vs.85).aspx
        if self.count() == 0:
            return 'Nothing to return'

        # Build a dictionary containing a summary of updates available
        results = {'Total': 0,
                   'Available': 0,
                   'Downloaded': 0,
                   'Installed': 0,
                   'Categories': {},
                   'Severity': {}}

        for update in self.updates:

            # Count the total number of updates available
            results['Total'] += 1

            # Updates available for download
            if not salt.utils.data.is_true(update.IsDownloaded) \
                    and not salt.utils.data.is_true(update.IsInstalled):
                results['Available'] += 1

            # Updates downloaded awaiting install
            if salt.utils.data.is_true(update.IsDownloaded) \
                    and not salt.utils.data.is_true(update.IsInstalled):
                results['Downloaded'] += 1

            # Updates installed
            if salt.utils.data.is_true(update.IsInstalled):
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


class WindowsUpdateAgent(object):
    '''
    Class for working with the Windows update agent

    '''
    # Error codes found at the following site:
    # https://msdn.microsoft.com/en-us/library/windows/desktop/hh968413(v=vs.85).aspx
    # https://technet.microsoft.com/en-us/library/cc720442(v=ws.10).aspx
    fail_codes = {-2145124300: 'Download failed: 0x80240034',
                  -2145124302: 'Invalid search criteria: 0x80240032',
                  -2145124305: 'Cancelled by policy: 0x8024002F',
                  -2145124307: 'Missing source: 0x8024002D',
                  -2145124308: 'Missing source: 0x8024002C',
                  -2145124312: 'Uninstall not allowed: 0x80240028',
                  -2145124315: 'Prevented by policy: 0x80240025',
                  -2145124316: 'No Updates: 0x80240024',
                  -2145124322: 'Service being shutdown: 0x8024001E',
                  -2145124325: 'Self Update in Progress: 0x8024001B',
                  -2145124327: 'Exclusive Install Conflict: 0x80240019',
                  -2145124330: 'Install not allowed: 0x80240016',
                  -2145124333: 'Duplicate item: 0x80240013',
                  -2145124341: 'Operation cancelled: 0x8024000B',
                  -2145124343: 'Operation in progress: 0x80240009',
                  -2145124284: 'Access Denied: 0x8024044',
                  -2145124283: 'Unsupported search scope: 0x80240045',
                  -2147024891: 'Access is denied: 0x80070005',
                  -2149843018: 'Setup in progress: 0x8024004A',
                  -4292599787: 'Install still pending: 0x00242015',
                  -4292607992: 'Already downloaded: 0x00240008',
                  -4292607993: 'Already uninstalled: 0x00240007',
                  -4292607994: 'Already installed: 0x00240006',
                  -4292607995: 'Reboot required: 0x00240005'}

    def __init__(self):
        '''
        Initialize the session and load all updates into the ``_updates``
        collection. This collection is used by the other class functions instead
        of querying Windows update (expensive).

        Need to look at the possibility of loading this into ``__context__``
        '''
        # Initialize the PyCom system
        pythoncom.CoInitialize()

        # Create a session with the Windows Update Agent
        self._session = win32com.client.Dispatch('Microsoft.Update.Session')

        # Create Collection for Updates
        self._updates = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        self.refresh()

    def updates(self):
        '''
        Get the contents of ``_updates`` (all updates) and puts them in an
        Updates class to expose the list and summary functions.

        Returns:
            Updates: An instance of the Updates class with all updates for the
            system.

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()
            updates = wua.updates()

            # To get a list
            updates.list()

            # To get a summary
            updates.summary()
        '''
        updates = Updates()
        found = updates.updates

        for update in self._updates:
            found.Add(update)

        return updates

    def refresh(self):
        '''
        Refresh the contents of the ``_updates`` collection. This gets all
        updates in the Windows Update system and loads them into the collection.
        This is the part that is slow.

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()
            wua.refresh()
        '''
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386526(v=vs.85).aspx
        search_string = 'Type=\'Software\' or ' \
                        'Type=\'Driver\''

        # Create searcher object
        searcher = self._session.CreateUpdateSearcher()
        self._session.ClientApplicationID = 'Salt: Load Updates'

        # Load all updates into the updates collection
        try:
            results = searcher.Search(search_string)
            if results.Updates.Count == 0:
                log.debug('No Updates found for:\n\t\t%s', search_string)
                return 'No Updates found: {0}'.format(search_string)
        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Search Failed: %s\n\t\t%s', failure_code, search_string)
            raise CommandExecutionError(failure_code)

        self._updates = results.Updates

    def available(self,
                  skip_hidden=True,
                  skip_installed=True,
                  skip_mandatory=False,
                  skip_reboot=False,
                  software=True,
                  drivers=True,
                  categories=None,
                  severities=None):
        '''
        Gets a list of all updates available on the system that match the passed
        criteria.

        Args:

            skip_hidden (bool): Skip hidden updates. Default is True

            skip_installed (bool): Skip installed updates. Default is True

            skip_mandatory (bool): Skip mandatory updates. Default is False

            skip_reboot (bool): Skip updates that can or do require reboot.
            Default is False

            software (bool): Include software updates. Default is True

            drivers (bool): Include driver updates. Default is True

            categories (list): Include updates that have these categories.
            Default is none (all categories).

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

            severities (list): Include updates that have these severities.
            Default is none (all severities).

                Severities include the following:

                * Critical
                * Important

        .. note:: All updates are either software or driver updates. If both
        ``software`` and ``drivers`` is False, nothing will be returned.

        Returns:

            Updates: An instance of Updates with the results of the search.

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()

            # Gets all updates and shows a summary
            updates = wua.available
            updates.summary()

            # Get a list of Critical updates
            updates = wua.available(categories=['Critical Updates'])
            updates.list()
        '''
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386099(v=vs.85).aspx
        updates = Updates()
        found = updates.updates

        for update in self._updates:

            if salt.utils.data.is_true(update.IsHidden) and skip_hidden:
                continue

            if salt.utils.data.is_true(update.IsInstalled) and skip_installed:
                continue

            if salt.utils.data.is_true(update.IsMandatory) and skip_mandatory:
                continue

            if salt.utils.data.is_true(
                    update.InstallationBehavior.RebootBehavior) and skip_reboot:
                continue

            if not software and update.Type == 1:
                continue

            if not drivers and update.Type == 2:
                continue

            if categories is not None:
                match = False
                for category in update.Categories:
                    if category.Name in categories:
                        match = True
                if not match:
                    continue

            if severities is not None:
                if update.MsrcSeverity not in severities:
                    continue

            found.Add(update)

        return updates

    def search(self, search_string):
        '''
        Search for either a single update or a specific list of updates. GUIDs
        are searched first, then KB numbers, and finally Titles.

        Args:

            search_string (str, list): The search string to use to find the
            update. This can be the GUID or KB of the update (preferred). It can
            also be the full Title of the update or any part of the Title. A
            partial Title search is less specific and can return multiple
            results.

        Returns:
            Updates: An instance of Updates with the results of the search

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()

            # search for a single update and show its details
            updates = wua.search('KB3194343')
            updates.list()

            # search for a list of updates and show their details
            updates = wua.search(['KB3195432', '12345678-abcd-1234-abcd-1234567890ab'])
            updates.list()
        '''
        updates = Updates()
        found = updates.updates

        if isinstance(search_string, six.string_types):
            search_string = [search_string]

        if isinstance(search_string, six.integer_types):
            search_string = [six.text_type(search_string)]

        for update in self._updates:

            for find in search_string:

                # Search by GUID
                if find == update.Identity.UpdateID:
                    found.Add(update)
                    continue

                # Search by KB
                if find in ['KB' + item for item in update.KBArticleIDs]:
                    found.Add(update)
                    continue

                # Search by KB without the KB in front
                if find in [item for item in update.KBArticleIDs]:
                    found.Add(update)
                    continue

                # Search by Title
                if find in update.Title:
                    found.Add(update)
                    continue

        return updates

    def download(self, updates):
        '''
        Download the updates passed in the updates collection. Load the updates
        collection using ``search`` or ``available``

        Args:

            updates (Updates): An instance of the Updates class containing a
            the updates to be downloaded.

        Returns:
            dict: A dictionary containing the results of the download

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()

            # Download KB3195454
            updates = wua.search('KB3195454')
            results = wua.download(updates)
        '''

        # Check for empty list
        if updates.count() == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to download'}
            return ret

        # Initialize the downloader object and list collection
        downloader = self._session.CreateUpdateDownloader()
        self._session.ClientApplicationID = 'Salt: Download Update'
        download_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        ret = {'Updates': {}}

        # Check for updates that aren't already downloaded
        for update in updates.updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid] = {}
            ret['Updates'][uid]['Title'] = update.Title
            ret['Updates'][uid]['AlreadyDownloaded'] = \
                bool(update.IsDownloaded)

            # Accept EULA
            if not salt.utils.data.is_true(update.EulaAccepted):
                log.debug('Accepting EULA: %s', update.Title)
                update.AcceptEula()  # pylint: disable=W0104

            # Update already downloaded
            if not salt.utils.data.is_true(update.IsDownloaded):
                log.debug('To Be Downloaded: %s', uid)
                log.debug('\tTitle: %s', update.Title)
                download_list.Add(update)

        # Check the download list
        if download_list.Count == 0:
            ret = {'Success': True,
                   'Updates': 'Nothing to download'}
            return ret

        # Send the list to the downloader
        downloader.Updates = download_list

        # Download the list
        try:
            log.debug('Downloading Updates')
            result = downloader.Download()
        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Download Failed: %s', failure_code)
            raise CommandExecutionError(failure_code)

        # Lookup dictionary
        result_code = {0: 'Download Not Started',
                       1: 'Download In Progress',
                       2: 'Download Succeeded',
                       3: 'Download Succeeded With Errors',
                       4: 'Download Failed',
                       5: 'Download Aborted'}

        log.debug('Download Complete')
        log.debug(result_code[result.ResultCode])
        ret['Message'] = result_code[result.ResultCode]

        # Was the download successful?
        if result.ResultCode in [2, 3]:
            log.debug('Downloaded Successfully')
            ret['Success'] = True
        else:
            log.debug('Download Failed')
            ret['Success'] = False

        # Report results for each update
        for i in range(download_list.Count):
            uid = download_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]

        return ret

    def install(self, updates):
        '''
        Install the updates passed in the updates collection. Load the updates
        collection using the ``search`` or ``available`` functions. If the
        updates need to be downloaded, use the ``download`` function.

        Args:

            updates (Updates): An instance of the Updates class containing a
            the updates to be installed.

        Returns:
            dict: A dictionary containing the results of the installation

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()

            # install KB3195454
            updates = wua.search('KB3195454')
            results = wua.download(updates)
            results = wua.install(updates)
        '''
        # Check for empty list
        if updates.count() == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to install'}
            return ret

        installer = self._session.CreateUpdateInstaller()
        self._session.ClientApplicationID = 'Salt: Install Update'
        install_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        ret = {'Updates': {}}

        # Check for updates that aren't already installed
        for update in updates.updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid] = {}
            ret['Updates'][uid]['Title'] = update.Title
            ret['Updates'][uid]['AlreadyInstalled'] = bool(update.IsInstalled)

            # Make sure the update has actually been installed
            if not salt.utils.data.is_true(update.IsInstalled):
                log.debug('To Be Installed: %s', uid)
                log.debug('\tTitle: %s', update.Title)
                install_list.Add(update)

        # Check the install list
        if install_list.Count == 0:
            ret = {'Success': True,
                   'Updates': 'Nothing to install'}
            return ret

        # Send the list to the installer
        installer.Updates = install_list

        # Install the list
        try:
            log.debug('Installing Updates')
            result = installer.Install()

        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Install Failed: %s', failure_code)
            raise CommandExecutionError(failure_code)

        # Lookup dictionary
        result_code = {0: 'Installation Not Started',
                       1: 'Installation In Progress',
                       2: 'Installation Succeeded',
                       3: 'Installation Succeeded With Errors',
                       4: 'Installation Failed',
                       5: 'Installation Aborted'}

        log.debug('Install Complete')
        log.debug(result_code[result.ResultCode])
        ret['Message'] = result_code[result.ResultCode]

        if result.ResultCode in [2, 3]:
            ret['Success'] = True
            ret['NeedsReboot'] = result.RebootRequired
            log.debug('NeedsReboot: %s', result.RebootRequired)
        else:
            log.debug('Install Failed')
            ret['Success'] = False

        reboot = {0: 'Never Reboot',
                  1: 'Always Reboot',
                  2: 'Poss Reboot'}
        for i in range(install_list.Count):
            uid = install_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]
            ret['Updates'][uid]['RebootBehavior'] = \
                reboot[install_list.Item(i).InstallationBehavior.RebootBehavior]

        return ret

    def uninstall(self, updates):
        '''
        Uninstall the updates passed in the updates collection. Load the updates
        collection using the ``search`` or ``available`` functions.

        .. note:: Starting with Windows 10 the Windows Update Agent is unable to
        uninstall updates. An ``Uninstall Not Allowed`` error is returned. If
        this error is encountered this function will instead attempt to use
        ``dism.exe`` to perform the uninstallation. ``dism.exe`` may fail to
        to find the KB number for the package. In that case, removal will fail.

        Args:

            updates (Updates): An instance of the Updates class containing a
            the updates to be uninstalled.

        Returns:
            dict: A dictionary containing the results of the uninstallation

        Code Example:

        .. code-block:: python

            import salt.utils.win_update
            wua = salt.utils.win_update.WindowsUpdateAgent()

            # uninstall KB3195454
            updates = wua.search('KB3195454')
            results = wua.uninstall(updates)
        '''
        # This doesn't work with the WUA API since Windows 10. It always returns
        # "0x80240028 # Uninstall not allowed". The full message is: "The update
        # could not be uninstalled because the request did not originate from a
        # Windows Server Update Services (WSUS) server.

        # Check for empty list
        if updates.count() == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to uninstall'}
            return ret

        installer = self._session.CreateUpdateInstaller()
        self._session.ClientApplicationID = 'Salt: Install Update'
        uninstall_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        ret = {'Updates': {}}

        # Check for updates that aren't already installed
        for update in updates.updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid] = {}
            ret['Updates'][uid]['Title'] = update.Title
            ret['Updates'][uid]['AlreadyUninstalled'] = \
                not bool(update.IsInstalled)

            # Make sure the update has actually been Uninstalled
            if salt.utils.data.is_true(update.IsInstalled):
                log.debug('To Be Uninstalled: %s', uid)
                log.debug('\tTitle: %s', update.Title)
                uninstall_list.Add(update)

        # Check the install list
        if uninstall_list.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to uninstall'}
            return ret

        # Send the list to the installer
        installer.Updates = uninstall_list

        # Uninstall the list
        try:
            log.debug('Uninstalling Updates')
            result = installer.Uninstall()

        except pywintypes.com_error as error:
            # Something happened, return error or try using DISM
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            # If "Uninstall Not Allowed" error, try using DISM
            if exc[5] == -2145124312:
                log.debug('Uninstall Failed with WUA, attempting with DISM')
                try:

                    # Go through each update...
                    for item in uninstall_list:

                        # Look for the KB numbers
                        for kb in item.KBArticleIDs:

                            # Get the list of packages
                            cmd = ['dism', '/Online', '/Get-Packages']
                            pkg_list = self._run(cmd)[0].splitlines()

                            # Find the KB in the pkg_list
                            for item in pkg_list:

                                # Uninstall if found
                                if 'kb' + kb in item.lower():
                                    pkg = item.split(' : ')[1]

                                    ret['DismPackage'] = pkg

                                    cmd = ['dism',
                                           '/Online',
                                           '/Remove-Package',
                                           '/PackageName:{0}'.format(pkg),
                                           '/Quiet',
                                           '/NoRestart']

                                    self._run(cmd)

                except CommandExecutionError as exc:
                    log.debug('Uninstall using DISM failed')
                    log.debug('Command: %s', ' '.join(cmd))
                    log.debug('Error: %s', exc)
                    raise CommandExecutionError(
                        'Uninstall using DISM failed: {0}'.format(exc))

                # DISM Uninstall Completed Successfully
                log.debug('Uninstall Completed using DISM')

                # Populate the return dictionary
                ret['Success'] = True
                ret['Message'] = 'Uninstalled using DISM'
                ret['NeedsReboot'] = needs_reboot()
                log.debug('NeedsReboot: %s', ret['NeedsReboot'])

                # Refresh the Updates Table
                self.refresh()

                reboot = {0: 'Never Reboot',
                          1: 'Always Reboot',
                          2: 'Poss Reboot'}

                # Check the status of each update
                for update in self._updates:
                    uid = update.Identity.UpdateID
                    for item in uninstall_list:
                        if item.Identity.UpdateID == uid:
                            if not update.IsInstalled:
                                ret['Updates'][uid]['Result'] = \
                                    'Uninstallation Succeeded'
                            else:
                                ret['Updates'][uid]['Result'] = \
                                    'Uninstallation Failed'
                            ret['Updates'][uid]['RebootBehavior'] = \
                                reboot[update.InstallationBehavior.RebootBehavior]

                return ret

            # Found a differenct exception, Raise error
            log.error('Uninstall Failed: %s', failure_code)
            raise CommandExecutionError(failure_code)

        # Lookup dictionary
        result_code = {0: 'Uninstallation Not Started',
                       1: 'Uninstallation In Progress',
                       2: 'Uninstallation Succeeded',
                       3: 'Uninstallation Succeeded With Errors',
                       4: 'Uninstallation Failed',
                       5: 'Uninstallation Aborted'}

        log.debug('Uninstall Complete')
        log.debug(result_code[result.ResultCode])
        ret['Message'] = result_code[result.ResultCode]

        if result.ResultCode in [2, 3]:
            ret['Success'] = True
            ret['NeedsReboot'] = result.RebootRequired
            log.debug('NeedsReboot: %s', result.RebootRequired)
        else:
            log.debug('Uninstall Failed')
            ret['Success'] = False

        reboot = {0: 'Never Reboot',
                  1: 'Always Reboot',
                  2: 'Poss Reboot'}
        for i in range(uninstall_list.Count):
            uid = uninstall_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]
            ret['Updates'][uid]['RebootBehavior'] = reboot[
                uninstall_list.Item(i).InstallationBehavior.RebootBehavior]

        return ret

    def _run(self, cmd):
        '''
        Internal function for running commands. Used by the uninstall function.

        Args:
            cmd (str, list): The command to run

        Returns:
            str: The stdout of the command
        '''

        if isinstance(cmd, six.string_types):
            cmd = salt.utils.args.shlex_split(cmd)

        try:
            log.debug(cmd)
            p = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            return p.communicate()

        except (OSError, IOError) as exc:
            log.debug('Command Failed: %s', ' '.join(cmd))
            log.debug('Error: %s', exc)
            raise CommandExecutionError(exc)


def needs_reboot():
    '''
    Determines if the system needs to be rebooted.

    Returns:

        bool: True if the system requires a reboot, False if not

    CLI Examples:

    .. code-block:: bash

        import salt.utils.win_update

        salt.utils.win_update.needs_reboot()

    '''
    # Initialize the PyCom system
    pythoncom.CoInitialize()

    # Create an AutoUpdate object
    obj_sys = win32com.client.Dispatch('Microsoft.Update.SystemInfo')
    return salt.utils.data.is_true(obj_sys.RebootRequired)
