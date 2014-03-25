# -*- coding: utf-8 -*-
'''
Management of the windows update agent.
=======================================

.. versionadded: (Helium)

Set windows updates to run by category. Default behavior is to install
all updates that do not require user interaction to complete. 

Optionally set ``category`` to a category of your choosing to only
install certain updates. default is all available updates.

In the example below, will install all Security and Critical Updates,
and download but not install standard updates.

Example::
        updates:
                win_update.install:
                        - categories: 
                                - 'Critical Updates'
                                - 'Security Updates'
                win_update.downloaded:
                        - categories:
                                - 'Updates'

You can also specify a number of features about the update to have a 
fine grain approach to specific types of updates. These are the following
features/states of updates available for configuring:
        'UI' - User interaction required, skipped by default
        'downloaded' - Already downloaded, skipped by default (downloading)
        'present' - Present on computer, included by default (installing)
        'installed' - Already installed, skipped by default
        'reboot' - Reboot required, included by default
        'hidden' - skip those updates that have been hidden.
        
        'software' - Software updates, included by default
        'driver' - driver updates, skipped by defautl

This example installs all driver updates that don't require a reboot:
Example::
        gryffindor:
                win_update.install:
                        - includes:
                                - driver: True
                                - software: False
                                - reboot: False


tl;dr: want to just have your computers update? add this your sls:
updates:
        win_update.install
        

'''

# Import Python libs
import tempfile
import subprocess
import logging
try:
        import win32com.client
        import win32api
        import win32con
        import pywintypes
        import threading
        import pythoncom
        HAS_DEPENDENCIES = True
except ImportError:
        HAS_DEPENDENCIES = False

import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'win_update'

def __virtual__():
        '''
        Only works on Windows systems
        '''
        if salt.utils.is_windows() and HAS_DEPENDENCIES:
                return __virtualname__
        return False

def _gather_update_categories(updateCollection):
        categories = []
        for i in range(updateCollection.Count):
                update = updateCollection.Item(i)
                for j in range(update.Categories.Count):
                        name = update.Categories.Item(j).Name
                        if name not in categories:
                                log.debug('found category: {0}'.format(name))
                                categories.append(name)
        return categories

# some known categories:
#       Updates
#       Windows 7
#       Critical Updates
#       Security Updates
#       Update Rollups

class PyWinUpdater:
        def __init__(self,categories=None,skipUI = True,skipDownloaded = True,
                        skipInstalled=True, skipReboot=False,skipPresent=True,
                        softwareUpdates=True, driverUpdates=False,skipHidden=True):
                log.debug('CoInitializing the pycom system')
                pythoncom.CoInitialize()
                
                self.skipUI = skipUI
                self.skipDownloaded = skipDownloaded
                self.skipInstalled = skipInstalled
                self.skipReboot = skipReboot
                self.skipPresent = skipPresent
                self.skipHidden = skipHidden
                
                self.softwareUpdates = softwareUpdates
                self.driverUpdates = driverUpdates
                self.categories = categories
                self.foundCategories = None
                
                
                log.debug('dispatching keeper to keep the session object.')
                self.keeper = win32com.client.Dispatch('Microsoft.Update.Session')
                
                log.debug('keeper got. Now creating a seeker to seek out the updates')
                self.seeker = self.keeper.CreateUpdateSearcher()
                
                #list of updates that are applicable by current settings.
                self.quaffle = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
                
                #list of updates to be installed.
                self.bludger = win32com.client.Dispatch('Microsoft.Update.UpdateColl')
                
                #the object responsible for fetching the actual downloads. 
                self.chaser = self.keeper.CreateUpdateDownloader()
                self.chaser.Updates = self.quaffle
                
                #the object responsible for the installing of the updates.
                self.beater = self.keeper.CreateUpdateInstaller()
                self.beater.Updates = self.bludger
                
                #the results of the download process
                self.points = None
                
                #the results of the installation process
                self.fouls = None

        def Search(self,searchString):
                try:
                        log.debug('beginning search of the passed string: {0}'.format(searchString))
                        self.golden_snitch = self.seeker.Search(searchString)
                        log.debug('search completed successfully.')
                except Exception as e:
                        log.info('search for updates failed. {0}'.format(str(e)))
                        return e
                
                log.debug('parsing results. {0} updates were found.'.format(
                    str(self.golden_snitch.Updates.Count)))
                try:
                        for update in self.golden_snitch.Updates:
                                if update.InstallationBehavior.CanRequestUserInput == True:
                                        log.debug('Skipped update {0}'.format(str(update)))
                                        continue
                                for category in update.Categories:
                                        if self.skipDownloaded and update.IsDownloaded:
                                                continue
                                        if self.categories == None or category.Name in self.categories:
                                                self.quaffle.Add(update)
                                                log.debug('added update {0}'.format(str(update)))
                        self.foundCategories = _gather_update_categories(self.quaffle)
                        return True
                except Exception as e:
                        log.info('parsing updates failed. {0}'.format(str(e)))
                        return e
                        
        def AutoSearch(self):
                search_string = ''
                searchParams = []
                if self.skipInstalled: searchParams.append('IsInstalled=0')
                else: searchParams.append('IsInstalled=1')
                if self.skipHidden: searchParams.append('IsHidden=0')
                else: searchParams.append('IsHidden=1')
                if self.skipReboot: searchParams.append('RebootRequired=1')
                else: searchParams.append('RebootRequired=0')
                if self.skipPresent: searchParams.append('IsPresent=0')
                else: searchParams.append('IsPresent=1')
                if len(searchParams) > 1:
                        for i in searchParams:
                                search_string += '{0} and '.format(i)
                else:
                        search_string += '{0} and '.format(searchParams[1])
                
                if self.softwareUpdates and self.driverUpdates:
                        search_string += 'Type=\'Software\' or Type=\'Driver\''
                elif self.softwareUpdates:
                        search_string += 'Type=\'Software\''
                elif self.driverUpdates:
                        search_string += 'Type=\'Driver\''
                else:
                        return False ##if there is no type, the is nothing to search.
                log.debug('generated search string: {0}'.format(search_string))
                return self.Search(search_string)

        def Download(self):
                try:
                        if self.quaffle.Count != 0:
                                self.points = self.chaser.Download()
                        else:
                                log.debug('Skipped downloading, all updates were already cached.')
                        return True
                except Exception as e:
                        log.debug('failed in the downloading {0}.'.format(str(e)))
                        return e
                
        def Install(self):
                try:
                        for update in self.golden_snitch.Updates:
                                if update.IsDownloaded:
                                        self.bludger.Add(update)
                        log.debug('Updates prepared. beginning installation')
                except Exception as e:
                        log.info('Preparing install list failed: {0}'.format(str(e)))
                        return e
                
                if self.bludger.Count != 0:
                        log.debug('Install list created, about to install')
                        updates = []
                        try:
                                self.fouls = self.beater.Install()
                                log.info('Installation of updates complete')
                                return True
                        except Exception as e:
                                log.info('Installation failed: {0}'.format(str(e)))
                                return e
                else:
                        log.info('no new updates.')
                        return True
        
        def GetInstallationResults(self):
                log.debug('bluger has {0} updates in it'.format(str(self.bludger.Count)))
                if self.bludger.Count == 0:
                        return {}
                for i in range(self.bludger.Count):
                        updates.append('{0}: {1}'.format(
                                str(self.fouls.GetUpdateResult(i).ResultCode),
                                str(self.bludger.Item(i).Title)))
                
                log.debug('Update results enumerated, now making a list to pass back')
                results = {}
                for i,update in enumerate(updates):
                        results['update {0}'.format(i)] = update
                
                log.debug('Update information complied. returning')
                return results

        def GetDownloadResults(self):
                for i in range(self.quaffle.Count):
                        updates.append('{0}: {1}'.format(
                                str(self.points.GetUpdateResult(i).ResultCode),
                                str(self.quaffle.Item(i).Title)))
                results = {}
                for i,update in enumerate(updates):
                        results['update {0}'.format(i)] = update
                return results

        def SetCategories(self,categories):
                self.categories = categories

        def GetCategories(self):
                return self.categories

        def GetAvailableCategories(self):
                return self.foundCategories

        def SetIncludes(self,includes):
                if includes:
                        for i in includes:
                                value = i[i.keys()[0]]
                                include = i.keys()[0]
                                self.SetInclude(include,value)
                                log.debug('was asked to set {0} to {1}'.format(include,value))

        def SetInclude(self,include,state):
                if include == 'UI': self.skipUI = state
                elif include == 'downloaded': self.skipDownloaded = state
                elif include == 'installed': self.skipInstalled = state
                elif include == 'reboot': self.skipReboot = state
                elif include == 'present': self.skipPresent = state
                elif include == 'software':self.softwareUpdates = state
                elif include == 'driver':self.driverUpdates = state
                log.debug('new search state: \n\tUI: {0}\n\tDownload: {1}\n\tInstalled: {2}\n\treboot :{3}\n\tPresent: {4}\n\tsoftware: {5}\n\tdriver: {6}'.format(
                        self.skipUI,self.skipDownloaded,self.skipInstalled,self.skipReboot,
                        self.skipPresent,self.softwareUpdates,self.driverUpdates))

def _search(quidditch,retries=5):
        passed = False
        clean = True
        comment = ''
        while passed != True:
                log.debug('Searching. tries left: {0}'.format(str(retries)))
                passed = quidditch.AutoSearch()
                log.debug('Done searching: {0}'.format(str(passed)))
                if isinstance(passed,Exception):
                        clean = False
                        comment += 'Failed in the seeking/parsing process:\n\t\t{0}\n'.format(str(passed))
                        retries -= 1
                        if retries:
                                comment += '{0} tries to go. retrying\n'.format(str(retries))
                                passed = False
                        else:
                                comment += 'out of retries. this update round failed.\n'
                                return (comment,True,retries)
                        passed = False
        if clean:
                comment += 'Search was done with out an error.\n'
        return (comment,True,retries)

def _download(quidditch,retries=5):
        passed = False
        clean = True
        comment = ''
        while not passed:
                log.debug('Downloading. tries left: {0}'.format(str(retries)))
                passed = quidditch.Download()
                log.debug('Done downloading: {0}'.format(str(passed)))
                if isinstance(passed,Exception):
                        clean = False
                        comment += 'Failed while trying to download updates:\n\t\t{0}\n'.format(str(passed))
                        retries -= 1
                        if retries:
                                comment += '{0} tries to go. retrying\n'.format(str(retries))
                                passed = False
                        else:
                                comment += 'out of retries. this update round failed.\n'
                                return (comment,False,retries)
        if clean:
                comment += 'Download was done without error.\n'
        return (comment,True,retries)
        
def _install(quidditch,retries=5):
        passed = False
        clean = True
        comment = ''
        while not passed:
                log.debug('quaffle is this long: {0}'.format(str(quidditch.bludger.Count)))
                log.debug('Installing. tries left: {0}'.format(str(retries)))
                passed = quidditch.Install()
                log.info('Done installing: {0}'.format(str(passed)))
                if isinstance(passed,Exception):
                        clean = False
                        comment += 'Failed while trying to install the updates.\n\t\t{0}\n'.format(str(passed))
                        retries -= 1
                        if retries:
                                comment += '{0} tries to go. retrying\n'.format(str(retries))
                                passed = False
                        else:
                                comment += 'out of retries. this update round failed.\n'
                                return (comment,False,retries)
        if clean:
                comment += 'Install was done without error.\n'
        return (comment,True,retries)


def install(name,categories=None,includes=None,retries=10):
        '''
        Install specified windows updates.
        '''
        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}
        log.debug('categories to search for are: '.format(str(categories)))
        quidditch = PyWinUpdater()
        quidditch.SetCategories(categories)
        quidditch.SetIncludes(includes)
        
        
        ##this is where we be seeking the things! yar!
        comment, passed, retries = _search(quidditch,retries)
        ret['comment'] += comment
        if not passed:
                ret['result'] = False
                return ret
        
        ##this is where we get all the things! i.e. download updates.
        comment, passed, retries = _download(quidditch,retries)
        ret['comment'] += comment
        if not passed:
                ret['result'] = False
                return ret

        ##this is where we put things in their place!
        comment, passed, retries = _install(quidditch,retries)
        ret['comment'] += comment
        if not passed:
                ret['result'] = False
                return ret

        try:
                ret['changes'] = quidditch.GetInstallationResults()
        except Exception as e:
                ret['comment'] += 'could not get results, but updates were installed.'
        return ret

def download(name,categories=None,includes=None,retries=10):
        '''
        Cache updates for later install. 
        '''
        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}
        log.debug('categories to search for are: '.format(str(categories)))
        quidditch = PyWinUpdater()
        quidditch.SetCategories(categories)
        quidditch.SetIncludes(includes)
        
        ##this is where we be seeking the things! yar!
        comment, passed, retries = _search(quidditch,retries)
        ret['comment'] += comment
        if not passed:
                ret['result'] = False
                return ret
        
        ##this is where we get all the things! i.e. download updates.
        comment, passed, retries = _download(quidditch,retries)
        ret['comment'] += comment
        if not passed:
                ret['result'] = False
                return ret
        
        try:
                ret['changes'] = quidditch.GetDownloadResults()
        except Exception as e:
                ret['comment'] += 'could not get results, but updates were downloaded.'
                
        return ret

#To the King#
