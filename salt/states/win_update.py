# -*- coding: utf-8 -*-
'''
Management of the windows update agent
======================================

This module is being deprecated and will be removed in Salt Fluorine. Please use
the ``win_wua`` state module instead.

.. versionadded:: 2014.7.0

Set windows updates to run by category. Default behavior is to install
all updates that do not require user interaction to complete.

Optionally set ``category`` to a category of your choice to only
install certain updates. Default is to set to install all available updates.

The following example will install all Security and Critical Updates,
and download but not install standard updates.

.. code-block:: yaml

    updates:
      win_update.installed:
        - categories:
          - 'Critical Updates'
          - 'Security Updates'
        - skips:
          - downloaded
      win_update.downloaded:
        - categories:
          - 'Updates'
        - skips:
          - downloaded

You can also specify a number of features about the update to have a
fine grain approach to specific types of updates. These are the following
features/states of updates available for configuring:

.. code-block:: text

    'UI' - User interaction required, skipped by default
    'downloaded' - Already downloaded, included by default
    'present' - Present on computer, skipped by default
    'installed' - Already installed, skipped by default
    'reboot' - Reboot required, included by default
    'hidden' - Skip updates that have been hidden, skipped by default
    'software' - Software updates, included by default
    'driver' - driver updates, included by default

The following example installs all driver updates that don't require a reboot:
.. code-block:: yaml

    gryffindor:
      win_update.installed:
        - skips:
          - driver: True
          - software: False
          - reboot: False

To just update your windows machine, add this your sls:

.. code-block:: yaml

    updates:
      win_update.installed
'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import 3rd-party libs
# pylint: disable=import-error
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
try:
    import win32com.client
    import pythoncom
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False
# pylint: enable=import-error

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return True
    return False


def _gather_update_categories(updateCollection):
    '''
    this is a convenience method to gather what categories of updates are available in any update
    collection it is passed. Typically though, the download_collection.
    Some known categories:
        Updates
        Windows 7
        Critical Updates
        Security Updates
        Update Rollups
    '''
    categories = []
    for i in range(updateCollection.Count):
        update = updateCollection.Item(i)
        for j in range(update.Categories.Count):
            name = update.Categories.Item(j).Name
            if name not in categories:
                log.debug('found category: {0}'.format(name))
                categories.append(name)
    return categories


class PyWinUpdater(object):
    def __init__(self, categories=None, skipUI=True, skipDownloaded=False,
            skipInstalled=True, skipReboot=False, skipPresent=False,
            skipSoftwareUpdates=False, skipDriverUpdates=False, skipHidden=True):
        log.debug('CoInitializing the pycom system')
        pythoncom.CoInitialize()

        # pylint: disable=invalid-name
        self.skipUI = skipUI
        self.skipDownloaded = skipDownloaded
        self.skipInstalled = skipInstalled
        self.skipReboot = skipReboot
        self.skipPresent = skipPresent
        self.skipHidden = skipHidden

        self.skipSoftwareUpdates = skipSoftwareUpdates
        self.skipDriverUpdates = skipDriverUpdates
        self.categories = categories
        self.foundCategories = None
        # pylint: enable=invalid-name

        log.debug('dispatching update_session to keep the session object.')
        self.update_session = win32com.client.Dispatch('Microsoft.Update.Session')

        log.debug('update_session got. Now creating a win_searcher to seek out the updates')
        self.win_searcher = self.update_session.CreateUpdateSearcher()

        # list of updates that are applicable by current settings.
        self.download_collection = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # list of updates to be installed.
        self.install_collection = win32com.client.Dispatch('Microsoft.Update.UpdateColl')

        # the object responsible for fetching the actual downloads.
        self.win_downloader = self.update_session.CreateUpdateDownloader()
        self.win_downloader.Updates = self.download_collection

        # the object responsible for the installing of the updates.
        self.win_installer = self.update_session.CreateUpdateInstaller()
        self.win_installer.Updates = self.install_collection

        # the results of the download process
        self.download_results = None

        # the results of the installation process
        self.install_results = None

    def Search(self, searchString):
        try:
            log.debug('beginning search of the passed string: {0}'.format(searchString))
            self.search_results = self.win_searcher.Search(searchString)
            log.debug('search completed successfully.')
        except Exception as exc:
            log.info('search for updates failed. {0}'.format(exc))
            return exc

        log.debug('parsing results. {0} updates were found.'.format(
            self.search_results.Updates.Count))
        try:
            for update in self.search_results.Updates:
                if update.InstallationBehavior.CanRequestUserInput:
                    log.debug(u'Skipped update {0}'.format(update.title))
                    continue
                for category in update.Categories:
                    if self.skipDownloaded and update.IsDownloaded:
                        continue
                    if self.categories is None or category.Name in self.categories:
                        self.download_collection.Add(update)
                        log.debug(u'added update {0}'.format(update.title))
            self.foundCategories = _gather_update_categories(self.download_collection)
            return True
        except Exception as exc:
            log.info('parsing updates failed. {0}'.format(exc))
            return exc

    def AutoSearch(self):
        search_string = ''
        searchParams = []
        if self.skipInstalled:
            searchParams.append('IsInstalled=0')
        else:
            searchParams.append('IsInstalled=1')

        if self.skipHidden:
            searchParams.append('IsHidden=0')
        else:
            searchParams.append('IsHidden=1')

        if self.skipReboot:
            searchParams.append('RebootRequired=0')
        else:
            searchParams.append('RebootRequired=1')

        if self.skipPresent:
            searchParams.append('IsPresent=0')
        else:
            searchParams.append('IsPresent=1')

        if len(searchParams) > 1:
            for i in searchParams:
                search_string += '{0} and '.format(i)
        else:
            search_string += '{0} and '.format(searchParams[1])

        if not self.skipSoftwareUpdates and not self.skipDriverUpdates:
            search_string += 'Type=\'Software\' or Type=\'Driver\''
        elif not self.skipSoftwareUpdates:
            search_string += 'Type=\'Software\''
        elif not self.skipDriverUpdates:
            search_string += 'Type=\'Driver\''
        else:
            return False
            # if there is no type, the is nothing to search.
        log.debug('generated search string: {0}'.format(search_string))
        return self.Search(search_string)

    def Download(self):
        try:
            if self.download_collection.Count != 0:
                self.download_results = self.win_downloader.Download()
            else:
                log.debug('Skipped downloading, all updates were already cached.')
            return True
        except Exception as exc:
            log.debug('failed in the downloading {0}.'.format(exc))
            return exc

    def Install(self):
        try:
            for update in self.search_results.Updates:
                if update.IsDownloaded:
                    self.install_collection.Add(update)
            log.debug('Updates prepared. beginning installation')
        except Exception as exc:
            log.info('Preparing install list failed: {0}'.format(exc))
            return exc

        # accept eula if not accepted
        try:
            for update in self.search_results.Updates:
                if not update.EulaAccepted:
                    log.debug(u'Accepting EULA: {0}'.format(update.Title))
                    update.AcceptEula()
        except Exception as exc:
            log.info('Accepting Eula failed: {0}'.format(exc))
            return exc

        if self.install_collection.Count != 0:
            log.debug('Install list created, about to install')
            updates = []
            try:
                self.install_results = self.win_installer.Install()
                log.info('Installation of updates complete')
                return True
            except Exception as exc:
                log.info('Installation failed: {0}'.format(exc))
                return exc
        else:
            log.info('no new updates.')
            return True

    def GetInstallationResults(self):
        log.debug('bluger has {0} updates in it'.format(self.install_collection.Count))
        updates = []
        if self.install_collection.Count == 0:
            return {}
        for i in range(self.install_collection.Count):
            updates.append('{0}: {1}'.format(
                self.install_results.GetUpdateResult(i).ResultCode,
                self.install_collection.Item(i).Title))

        log.debug('Update results enumerated, now making a list to pass back')
        results = {}
        for i, update in enumerate(updates):
            results['update {0}'.format(i)] = update

        log.debug('Update information complied. returning')
        return results

    def GetDownloadResults(self):
        updates = []
        for i in range(self.download_collection.Count):
            updates.append('{0}: {1}'.format(
                self.download_results.GetUpdateResult(i).ResultCode,
                self.download_collection.Item(i).Title))
        results = {}
        for i, update in enumerate(updates):
            results['update {0}'.format(i)] = update
        return results

    def SetCategories(self, categories):
        self.categories = categories

    def GetCategories(self):
        return self.categories

    def GetAvailableCategories(self):
        return self.foundCategories

    def SetSkips(self, skips):
        if skips:
            for i in skips:
                value = i[next(six.iterkeys(i))]
                skip = next(six.iterkeys(i))
                self.SetSkip(skip, value)
                log.debug('was asked to set {0} to {1}'.format(skip, value))

    def SetSkip(self, skip, state):
        if skip == 'UI':
            self.skipUI = state
        elif skip == 'downloaded':
            self.skipDownloaded = state
        elif skip == 'installed':
            self.skipInstalled = state
        elif skip == 'reboot':
            self.skipReboot = state
        elif skip == 'present':
            self.skipPresent = state
        elif skip == 'hidden':
            self.skipHidden = state
        elif skip == 'software':
            self.skipSoftwareUpdates = state
        elif skip == 'driver':
            self.skipDriverUpdates = state
        log.debug('new search state: \n\tUI: {0}\n\tDownload: {1}\n\tInstalled: {2}\n\treboot :{3}\n\tPresent: {4}\n\thidden: {5}\n\tsoftware: {6}\n\tdriver: {7}'.format(
            self.skipUI, self.skipDownloaded, self.skipInstalled, self.skipReboot,
            self.skipPresent, self.skipHidden, self.skipSoftwareUpdates, self.skipDriverUpdates))


def _search(win_updater, retries=5):
    passed = False
    clean = True
    comment = ''
    while not passed:
        log.debug('Searching. tries left: {0}'.format(retries))
        passed = win_updater.AutoSearch()
        log.debug('Done searching: {0}'.format(passed))
        if isinstance(passed, Exception):
            clean = False
            comment += 'Failed in the seeking/parsing process:\n\t\t{0}\n'.format(passed)
            retries -= 1
            if retries:
                comment += '{0} tries to go. retrying\n'.format(retries)
                passed = False
            else:
                comment += 'out of retries. this update round failed.\n'
                return (comment, True, retries)
            passed = False
    if clean:
        comment += 'Search was done without error.\n'
    return (comment, True, retries)


def _download(win_updater, retries=5):
    passed = False
    clean = True
    comment = ''
    while not passed:
        log.debug('Downloading. tries left: {0}'.format(retries))
        passed = win_updater.Download()
        log.debug('Done downloading: {0}'.format(passed))
        if isinstance(passed, Exception):
            clean = False
            comment += 'Failed while trying to download updates:\n\t\t{0}\n'.format(passed)
            retries -= 1
            if retries:
                comment += '{0} tries to go. retrying\n'.format(retries)
                passed = False
            else:
                comment += 'out of retries. this update round failed.\n'
                return (comment, False, retries)
    if clean:
        comment += 'Download was done without error.\n'
    return (comment, True, retries)


def _install(win_updater, retries=5):
    passed = False
    clean = True
    comment = ''
    while not passed:
        log.debug('download_collection is this long: {0}'.format(win_updater.install_collection.Count))
        log.debug('Installing. tries left: {0}'.format(retries))
        passed = win_updater.Install()
        log.info('Done installing: {0}'.format(passed))
        if isinstance(passed, Exception):
            clean = False
            comment += 'Failed while trying to install the updates.\n\t\t{0}\n'.format(passed)
            retries -= 1
            if retries:
                comment += '{0} tries to go. retrying\n'.format(retries)
                passed = False
            else:
                comment += 'out of retries. this update round failed.\n'
                return (comment, False, retries)
    if clean:
        comment += 'Install was done without error.\n'
    return (comment, True, retries)


def installed(name, categories=None, skips=None, retries=10):
    '''
    Install specified windows updates.

    name:
        if categories is left empty, it will be assumed that you are passing the category option
        through the name. These are separate because you can only have one name, but can have
        multiple categories.

    categories:
        the list of categories to be downloaded. These are simply strings in the update's
        information, so there is no enumeration of the categories available. Some known categories:

        .. code-block:: text

            Updates
            Windows 7
            Critical Updates
            Security Updates
            Update Rollups

    skips:
        a list of features of the updates to cull by. Available features:

        .. code-block:: text

            'UI' - User interaction required, skipped by default
            'downloaded' - Already downloaded, skipped by default (downloading)
            'present' - Present on computer, included by default (installing)
            'installed' - Already installed, skipped by default
            'reboot' - Reboot required, included by default
            'hidden' - skip those updates that have been hidden.
            'software' - Software updates, included by default
            'driver' - driver updates, skipped by default

    retries
        Number of retries to make before giving up. This is total, not per
        step.
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    deprecation_msg = 'The \'win_update\' module is deprecated, and will be ' \
                      'removed in Salt Fluorine. Please use the \'win_wua\' ' \
                      'module instead.'
    salt.utils.warn_until('Fluorine', deprecation_msg)
    ret.setdefault('warnings', []).append(deprecation_msg)
    if not categories:
        categories = [name]
    log.debug('categories to search for are: {0}'.format(categories))
    win_updater = PyWinUpdater()
    win_updater.SetCategories(categories)
    win_updater.SetSkips(skips)

    # this is where we be seeking the things! yar!
    comment, passed, retries = _search(win_updater, retries)
    ret['comment'] += comment
    if not passed:
        ret['result'] = False
        return ret

    # this is where we get all the things! i.e. download updates.
    comment, passed, retries = _download(win_updater, retries)
    ret['comment'] += comment
    if not passed:
        ret['result'] = False
        return ret

    # this is where we put things in their place!
    comment, passed, retries = _install(win_updater, retries)
    ret['comment'] += comment
    if not passed:
        ret['result'] = False
        return ret

    try:
        ret['changes'] = win_updater.GetInstallationResults()
    except Exception:
        ret['comment'] += 'could not get results, but updates were installed.'
    return ret


def downloaded(name, categories=None, skips=None, retries=10):
    '''
    Cache updates for later install.

    name:
        if categories is left empty, it will be assumed that you are passing the category option
        through the name. These are separate because you can only have one name, but can have
        multiple categories.

    categories:
        the list of categories to be downloaded. These are simply strings in the update's
        information, so there is no enumeration of the categories available. Some known categories:

        .. code-block:: text

            Updates
            Windows 7
            Critical Updates
            Security Updates
            Update Rollups

    skips:
        a list of features of the updates to cull by. Available features:

        .. code-block:: text

            'UI' - User interaction required, skipped by default
            'downloaded' - Already downloaded, skipped by default (downloading)
            'present' - Present on computer, included by default (installing)
            'installed' - Already installed, skipped by default
            'reboot' - Reboot required, included by default
            'hidden' - skip those updates that have been hidden.
            'software' - Software updates, included by default
            'driver' - driver updates, skipped by default

    retries
        Number of retries to make before giving up. This is total, not per
        step.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    deprecation_msg = 'The \'win_update\' module is deprecated, and will be ' \
                      'removed in Salt Fluorine. Please use the \'win_wua\' ' \
                      'module instead.'
    salt.utils.warn_until('Fluorine', deprecation_msg)
    ret.setdefault('warnings', []).append(deprecation_msg)

    if not categories:
        categories = [name]
    log.debug('categories to search for are: {0}'.format(categories))
    win_updater = PyWinUpdater()
    win_updater.SetCategories(categories)
    win_updater.SetSkips(skips)

    # this is where we be seeking the things! yar!
    comment, passed, retries = _search(win_updater, retries)
    ret['comment'] += comment
    if not passed:
        ret['result'] = False
        return ret

    # this is where we get all the things! i.e. download updates.
    comment, passed, retries = _download(win_updater, retries)
    ret['comment'] += comment
    if not passed:
        ret['result'] = False
        return ret

    try:
        ret['changes'] = win_updater.GetDownloadResults()
    except Exception:
        ret['comment'] += 'could not get results, but updates were downloaded.'

    return ret
