# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging

import win32com.client
import pythoncom
import pywintypes

import salt.utils
from salt.ext import six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


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
    update_types = {1: 'Software',
                    2: 'Driver'}
    reboot_behavior = {0: 'Never Requires Reboot',
                       1: 'Always Requires Reboot',
                       2: 'Can Require Reboot'}

    def __init__(self):
        # Initialize the PyCom system
        pythoncom.CoInitialize()

        # Create a session with the Windows Update Agent
        self._session = win32com.client.Dispatch('Microsoft.Update.Session')

        # Create Collection for Updates
        self._updates = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
        self._found = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
        self._download = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
        self._install = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        self._load_all_updates()

    def _load_all_updates(self):
        # Load all updates
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

    def search(self, search_string):

        found = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        if self._updates.Count == 0:
            self._load_all_updates()

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

        self._found = found

    def updates_details(self):
        return self._details(self._updates)

    def found_details(self):
        return self._details(self._found)

    def _details(self, updates):

        if updates.Count == 0:
            return 'Nothing to return'

        log.debug('Building a detailed report of the results.')

        # Build a dictionary containing details for each update
        results = {}
        for update in updates:

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
                    self.reboot_behavior[update.InstallationBehavior.RebootBehavior],
                'KB': ['KB' + item for item in update.KBArticleIDs],
                'Categories': [item.Name for item in update.Categories]
            }

        return results

    def updates_summary(self):
        return self._summary(self._updates)

    def found_summary(self):
        return self._summary(self._found)

    def _summary(self, updates):

        if updates.Count == 0:
            return 'Nothing to return'

        # Build a dictionary containing a summary of updates available
        results = {'Total': 0,
                   'Available': 0,
                   'Downloaded': 0,
                   'Installed': 0,
                   'Categories': {},
                   'Severity': {}}

        for update in updates:

            # Count the total number of updates available
            results['Total'] += 1

            # Updates available for download
            if not salt.utils.is_true(update.IsDownloaded)\
                    and not salt.utils.is_true(update.IsInstalled):
                results['Available'] += 1

            # Updates downloaded awaiting install
            if salt.utils.is_true(update.IsDownloaded)\
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

    def download_updates(self):
        return self._download(self._updates)

    def download_found(self):
        return self._download(self._found)

    def _download(self, updates):
        # Lookup dictionaries
        result_code = {0: 'Download Not Started',
                       1: 'Download In Progress',
                       2: 'Download Succeeded',
                       3: 'Download Succeeded With Errors',
                       4: 'Download Failed',
                       5: 'Download Aborted'}

        # Check for empty list
        if updates.Count == 0:
            return 'Nothing to download'

        # Initialize the downloader object and list collection
        downloader = self._session.CreateUpdateDownloader()
        self._session.ClientApplicationID = 'Salt: Download Update'
        download_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # Check for updates that aren't already downloaded
        for update in updates.Updates:
            if not salt.utils.is_true(update.IsDownloaded):
                download_list.Add(update)

        # Check the download list
        if download_list.Count == 0:
            return 'Nothing to download'

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

        log.debug('Download Complete')
        log.debug(result_code[result.ResultCode])

        # Was the download successful?
        if result.ResultCode in [2, 3]:
            ret['Success'] = True
        else:
            ret['Success'] = False

        ret['Message'] = result_code[result.ResultCode]

        # Report results for each update
        for i in range(download_list.Count):
            uid = download_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]

        return ret

    def install_updates(self):
        return self._install(self._updates)

    def install_found(self):
        return self._install(self._found)

    def _install(self, updates):
        if updates.Count == 0:
            return 'Nothing to install'

        installer = self._session.CreateUpdateInstaller()
        self._session.ClientApplicationID = 'Salt: Install Update'
        install_list = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # Install the updates
        for update in updates:
            # Make sure the update has actually been downloaded
            if not salt.utils.is_true(update.IsInstalled):
                install_list.Add(update)

        if install_list.Count == 0:
            return 'Nothing to install'

        installer.Updates = install_list

        # Try to run the installer
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

        result_code = {0: 'Installation Not Started',
                       1: 'Installation In Progress',
                       2: 'Installation Succeeded',
                       3: 'Installation Succeeded With Errors',
                       4: 'Installation Failed',
                       5: 'Installation Aborted'}

        log.debug('Install Complete')
        log.debug(result_code[result.ResultCode])

        if result.ResultCode in [2, 3]:
            ret['Success'] = True
            ret['NeedsReboot'] = result.RebootRequired
            log.debug('NeedsReboot: {0}'.format(result.RebootRequired))
        else:
            ret['Success'] = False

        ret['Message'] = result_code[result.ResultCode]
        reboot = {0: 'Never Reboot',
                  1: 'Always Reboot',
                  2: 'Poss Reboot'}
        for i in range(wua_install_list.Count):
            uid = wua_install_list.Item(i).Identity.UpdateID
            ret['Updates'][uid]['Result'] = \
                result_code[result.GetUpdateResult(i).ResultCode]
            ret['Updates'][uid]['RebootBehavior'] = \
                reboot[wua_install_list.Item(i).InstallationBehavior.RebootBehavior]

        return ret

wua = WUA()
wua.search('28cf1b09-2b1a-458c-9bd1-971d1b26b211')
print(wua.list_found())
print(wua.summary_found())
# print(wua.download())
# print(wua.install())
