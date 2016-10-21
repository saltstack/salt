# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging

try:
    import win32com.client
    import pythoncom
    import pywintypes
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

import salt.utils
from salt.ext import six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


class Updates:

    update_types = {1: 'Software',
                    2: 'Driver'}

    reboot_behavior = {0: 'Never Requires Reboot',
                       1: 'Always Requires Reboot',
                       2: 'Can Require Reboot'}

    def __init__(self):
        self.updates = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

    def count(self):
        return self.updates.Count

    def list(self):
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa386099(v=vs.85).aspx
        if self.count() == 0:
            return 'Nothing to return'

        log.debug('Building a detailed report of the results.')

        # Build a dictionary containing details for each update
        results = {}
        for update in self.updates:

            results[update.Identity.UpdateID] = {
                'guid': update.Identity.UpdateID,
                'Title': str(update.Title),
                'Type': self.update_types[update.Type],
                'Description': update.Description,
                'Downloaded': bool(update.IsDownloaded),
                'Installed': bool(update.IsInstalled),
                'Mandatory': bool(update.IsMandatory),
                'EULAAccepted': bool(update.EulaAccepted),
                'NeedsReboot': bool(update.RebootRequired),
                'Severity': str(update.MsrcSeverity),
                'UserInput':
                    bool(update.InstallationBehavior.CanRequestUserInput),
                'RebootBehavior':
                    self.reboot_behavior[
                        update.InstallationBehavior.RebootBehavior],
                'KB': ['KB' + item for item in update.KBArticleIDs],
                'Categories': [item.Name for item in update.Categories]
            }

        return results

    def summary(self):
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
            if not salt.utils.is_true(update.IsDownloaded) \
                    and not salt.utils.is_true(update.IsInstalled):
                results['Available'] += 1

            # Updates downloaded awaiting install
            if salt.utils.is_true(update.IsDownloaded) \
                    and not salt.utils.is_true(update.IsInstalled):
                results['Downloaded'] += 1

            # Updates installed
            if salt.utils.is_true(update.IsInstalled):
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

class WindowsUpdateAgent:
    # Error codes found at the following site:
    # https://msdn.microsoft.com/en-us/library/windows/desktop/hh968413(v=vs.85).aspx
    fail_codes = {-2145124300: 'Download failed: 0x80240034',
                  -2145124302: 'Invalid search criteria: 0x80240032',
                  -2145124305: 'Cancelled by policy: 0x8024002F',
                  -2145124307: 'Missing source: 0x8024002D',
                  -2145124308: 'Missing source: 0x8024002C',
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
                  -2149843018: 'Setup in progress: 0x8024004A',
                  -4292599787: 'Install still pending: 0x00242015',
                  -4292607992: 'Already downloaded: 0x00240008',
                  -4292607993: 'Already uninstalled: 0x00240007',
                  -4292607994: 'Already installed: 0x00240006',
                  -4292607995: 'Reboot required: 0x00240005'}

    def __init__(self):
        # Initialize the PyCom system
        pythoncom.CoInitialize()

        # Create a session with the Windows Update Agent
        self._session = win32com.client.Dispatch('Microsoft.Update.Session')

        # Create Collection for Updates
        self._updates = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        self._load_all_updates()

    def _load_all_updates(self):
        # Load all updates
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
                log.debug('No Updates found for:\n\t\t{0}'.format(search_list))
                return 'No Updates found: {0}'.format(search_list)
        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Search Failed: {0}\n\t\t{1}'.format(
                failure_code, search_list))
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

        updates = Updates()
        found = updates.updates

        for update in self._updates:

            if salt.utils.is_true(update.IsHidden) and skip_hidden:
                continue

            if salt.utils.is_true(update.IsInstalled) and skip_installed:
                continue

            if salt.utils.is_true(update.IsMandatory) and skip_mandatory:
                continue

            if salt.utils.is_true(update.RebootRequired) and skip_reboot:
                continue

            if not software and update.Type == 1:
                continue

            if not drivers and update.Type == 2:
                continue

            if categories is not None:
                match = false
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

        updates = Updates()
        found = updates.updates

        if isinstance(search_string, six.string_types):
            search_string = [search_string]

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

        # Check for empty list
        if updates.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to download'}
            return ret

        # Initialize the downloader object and list collection
        downloader = self._session.CreateUpdateDownloader()
        self._session.ClientApplicationID = 'Salt: Download Update'
        download_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # Check for updates that aren't already downloaded
        for update in updates.Updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid]['Title'] = update.Title

            # Accept EULA
            if not salt.utils.is_true(updates.EulaAccepted):
                log.debug('Accepting EULA: {0}'.format(update.Title))
                update.AcceptEula()  # pylint: disable=W0104

            # Update already downloaded
            ret['Updates'][uid]['AlreadyDownloaded'] = True
            if not salt.utils.is_true(update.IsDownloaded):
                log.debug('To Be Downloaded: {0}'.format(uid))
                log.debug('\tTitle: {0}'.format(update.Title))
                ret['Updates'][uid]['AlreadyDownloaded'] = False
                download_list.Add(update)

        # Check the download list
        if download_list.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to download'}
            return ret

        # Send the list to the downloader
        downloader.Updates = download_list

        # Download the list
        try:
            result = downloader.Download()
        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Download Failed: {0}'.format(failure_code))
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
            ret['Success'] = True
        else:
            ret['Success'] = False

        # Report results for each update
        for i in range(download_list.Count):
            uid = download_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]

        return ret

    def install(self, updates):

        # Check for empty list
        if updates.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to install'}
            return ret

        installer = self._session.CreateUpdateInstaller()
        self._session.ClientApplicationID = 'Salt: Install Update'
        install_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # Check for updates that aren't already installed
        for update in updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid]['Title'] = update.Title

            # Make sure the update has actually been installed
            ret['Updates'][uid]['AlreadyInstalled'] = True
            if not salt.utils.is_true(update.IsInstalled):
                log.debug('To Be Installed: {0}'.format(uid))
                log.debug('\tTitle: {0}'.format(update.Title))
                ret['Updates'][uid]['AlreadyInstalled'] = False
                install_list.Add(update)

        # Check the install list
        if install_list.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to install'}
            return ret

        # Send the list to the installer
        installer.Updates = install_list

        # Install the list
        try:
            result = installer.Install()

        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Install Failed: {0}'.format(failure_code))
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
            log.debug('NeedsReboot: {0}'.format(result.RebootRequired))
        else:
            ret['Success'] = False

        reboot = {0: 'Never Reboot',
                  1: 'Always Reboot',
                  2: 'Poss Reboot'}
        for i in range(install_list.Count):
            uid = install_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]
            ret['Updates'][uid]['RebootBehavior'] = reboot[
                install_list.Item(i).InstallationBehavior.RebootBehavior]

        return ret

    def uninstall(self, updates):

        # Check for empty list
        if updates.Count == 0:
            ret = {'Success': False,
                   'Updates': 'Nothing to uninstall'}
            return ret

        installer = self._session.CreateUpdateInstaller()
        self._session.ClientApplicationID = 'Salt: Install Update'
        uninstall_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # Check for updates that aren't already installed
        for update in updates:

            # Define uid to keep the lines shorter
            uid = update.Identity.UpdateID
            ret['Updates'][uid]['Title'] = update.Title

            # Make sure the update has actually been installed
            ret['Updates'][uid]['AlreadyUninstalled'] = True
            if salt.utils.is_true(update.IsInstalled):
                log.debug('To Be Uninstalled: {0}'.format(uid))
                log.debug('\tTitle: {0}'.format(update.Title))
                ret['Updates'][uid]['AlreadyUninstalled'] = False
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
            result = installer.Uninstall()

        except pywintypes.com_error as error:
            # Something happened, raise an error
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            try:
                failure_code = self.fail_codes[exc[5]]
            except KeyError:
                failure_code = 'Unknown Failure: {0}'.format(error)

            log.error('Uninstall Failed: {0}'.format(failure_code))
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
            log.debug('NeedsReboot: {0}'.format(result.RebootRequired))
        else:
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
