# -*- coding: utf-8 -*-
'''
Module for running windows updates.

:depends:   - win32com
            - win32con
            - win32api
            - pywintypes

.. versionadded: (Helium)

Note about naming convention used internally to this module:
You will notice rather quickly that many of the names in this module have been named after various
aspects of the sport 'Quidditch' from the fantasy series 'Harry Potter'. If you are unfamiliar with
Quidditch, I addvise you go read about it on wikipedia as a basic knowledge of it will help you
to understand what is going on. 

Why did I do this you may ask? Clearity. Which sounds backwards. But variable names that are long
and not incredibly conceptually accurate 'searcher', 'updates found', 'updates downloaded', 
'updates to be downloaded','updates that are installed','updates that are downloaded, but not 
installed, but are going to be installed', etc. are not helpful.

So I provide you with a simple game of Quidditch to keep things understandable. here are roughly
what the variables I use are and what they do:

Quidditch: the instance of the python windows updater class.

Players:
Keeper: the master variable that manages the update session.
Seeker: the handle to the windows update agent (WUA) object responsible for doing the searches.
Chaser: the handle to the WUA object responsible for managing the download of updates.
Beater: the handle to the WUA object that is given the task of installing the windows updates to
        the system the script is run on. Name was partly choosen as a joke against windows.

golden_snitch: what the seeker seeks. So the results of the search from the WUA object.
quaffle: what the chasers chase. The list of updates to be downloaded.
Bluger: what the beaters beat. The list of updates that are ready to be installed.

points: the results of the download process. i.e. getting the quaffle through the hoop.
fouls: results of the installation process. i.e. hitting other players. still. joke against windows

'''

# Import Python libs
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

#this is a convenience method to gather what categories of updates are available in any update
# collection it is passed. Typically though, the quaffle.
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
                
                #the list of categories that the user wants to be searched for.
                self.categories = categories
                
                #the list of categories that are present in the updates found.
                self.foundCategories = []
                
                #careful not to get those two confused.
                
                
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
                        #step through the list of the updates to ensure that the updates match the
                        # features desired.
                        for update in self.golden_snitch.Updates:
                                #this skipps an update if UI updates are not desired.
                                if update.InstallationBehavior.CanRequestUserInput == True:
                                        log.debug('Skipped update {0}'.format(str(update)))
                                        continue
                                
                                #if this update is already downloaded, it doesn't need to be in 
                                # the quaffle. so skipping it unless the user mandates redownload.
                                if self.skipDownloaded and update.IsDownloaded:
                                        continue
                                
                                #check this update's categories aginst the ones desired.
                                for category in update.Categories:
                                        #this is a zero gaurd. these tests have to be in this order
                                        # or it will error out when the user tries to search for 
                                        # updates with out specifying categories.
                                        if self.categories == None or category.Name in self.categories:
                                                #adds it to the list to be downloaded.
                                                self.quaffle.Add(update)
                                                log.debug('added update {0}'.format(str(update)))
                                                #ever update has 2 categories. this prevents the
                                                #from being added twice.
                                                break;
                        log.debug('quaffle made. gathering found categories.')
                        
                        #gets the categories of the updates available in this collection of updates
                        self.foundCategories = _gather_update_categories(self.quaffle)
                        log.debug('found categories: {0}'.format(str(self.foundCategories)))
                        return True
                except Exception as e:
                        log.info('parsing updates failed. {0}'.format(str(e)))
                        return e
                        
        def AutoSearch(self):
                #this function generates a search string. simplifying the search function while
                #still providing as many features as possible.
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
                #chase the quaffle! do the actual download process.
                try:
                        #if the quaffle is empty. no need to download things.
                        if self.quaffle.Count != 0:
                                self.points = self.chaser.Download()
                        else:
                                log.debug('Skipped downloading, all updates were already cached.')
                        return True
                except Exception as e:
                        log.debug('failed in the downloading {0}.'.format(str(e)))
                        return e
                
        def Install(self):
                #beat those updates into place!
                try:
                        #this does not draw from the quaffle. important thing to know.
                        #the blugger is created regardless of what the quaffle has done. but it
                        #will only download those updates which have been downloaded and are ready.
                        for update in self.golden_snitch.Updates:
                                if update.IsDownloaded:
                                        self.bludger.Add(update)
                        log.debug('Updates prepared. beginning installation')
                except Exception as e:
                        log.info('Preparing install list failed: {0}'.format(str(e)))
                        return e
                
                #if the blugger is empty. no point it starting the install process.
                if self.bludger.Count != 0:
                        log.debug('Install list created, about to install')
                        updates = []
                        try:
                                #the call to install.
                                self.fouls = self.beater.Install()
                                log.info('Installation of updates complete')
                                return True
                        except Exception as e:
                                log.info('Installation failed: {0}'.format(str(e)))
                                return e
                else:
                        log.info('no new updates.')
                        return True
        
        #this gets results of installation process.
        def GetInstallationResults(self):
                #if the blugger is empty, the results are nil.
                log.debug('bluger has {0} updates in it'.format(str(self.bludger.Count)))
                if self.bludger.Count == 0:
                        return {}
                
                updates = []
                log.debug('reparing update list')
                for i in range(self.bludger.Count):
                        #this gets the result from fouls, but the title comes from the update
                        #collection bludger.
                        updates.append('{0}: {1}'.format(
                                str(self.fouls.GetUpdateResult(i).ResultCode),
                                str(self.bludger.Item(i).Title)))
                
                log.debug('Update results enumerated, now making a library to pass back')
                results = {}
                
                #translates the list of update results into a library that salt expects.
                for i,update in enumerate(updates):
                        results['update {0}'.format(i)] = update
                
                log.debug('Update information complied. returning')
                return results
        
        #converts the installation results into a pretty print.
        def GetInstallationResultsPretty(self):
                updates = self.GetInstallationResults()
                ret = 'The following are the updates and their return codes.\n'
                for i in updates.keys():
                        ret += '\t{0} : {1}\n'.format(str(updates[i].ResultCode),str(updates[i].Title))
                return ret

        def GetDownloadResults(self):
                for i in range(self.quaffle.Count):
                        updates.append('{0}: {1}'.format(
                                str(self.points.GetUpdateResult(i).ResultCode),
                                str(self.quaffle.Item(i).Title)))
                results = {}
                for i,update in enumerate(updates):
                        results['update {0}'.format(i)] = update
                return results
                
        def GetSearchResults(self):
                updates = []
                log.debug('parsing results. {0} updates were found.'.format(
                        str(self.quaffle.count)))
                
                for update in self.quaffle:
                        if update.InstallationBehavior.CanRequestUserInput == True:
                                log.debug('Skipped update {0}'.format(str(update)))
                                continue
                        updates.append(str(update))
                        log.debug('added update {0}'.format(str(update)))
                return updates
        
        def GetSearchResultsPretty(self):
                updates = self.GetSearchResults()
                ret = 'There are {0} updates. they are as follows:\n'.format(str(len(updates)))
                for update in updates:
                        ret += '\t{0}\n'.format(str(update))
                return ret

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
        
        def __str__(self):
                updates = []
                results = 'There are {0} updates, by category there are:\n'.format(
                        str(self.quaffle.count))
                for category in self.foundCategories:
                        count = 0
                        for update in self.quaffle:
                                for c in update.Categories:
                                        if category == c.Name:
                                                count += 1
                        results += '\t{0}: {1}\n'.format(category,count)
                return results

#a wrapper method for the pywinupdater class. I might move this into the class, but right now,
#that is to much for one class I think.
def _search(quidditch,retries=5):
        passed = False
        clean = True
        comment = ''
        while passed != True:
                log.debug('Searching. tries left: {0}'.format(str(retries)))
                #let the updater make it's own search string. MORE POWER this way.
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
                #bragging rights.
                comment += 'Search was done with out an error.\n'
        
        return (comment,True,retries)

#another wrapper method. 
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

#and the last wrapper method. keeping things simple.
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

#this is where the actual functions available to salt begin.
def list_updates(verbose=False,includes=None,retries=5,categories=None):
        '''
        Returns a summary of available updates, grouped into their non-mutually
        exclusive categories. 
        
        To list the actual updates by name, add 'verbose' to the call.
        
        you can set the maximum number of retries to n in the search process by 
        adding: retries=n
        
        various aspects of the updates can be included or excluded. this feature is
        still indevelopment.
        
        You can also specify by category of update similarly to how you do includes:
        categories=['Windows 7','Security Updates']
        Some known categories:
                        Updates
                        Windows 7
                        Critical Updates
                        Security Updates
                        Update Rollups
        
        CLI Example:
        Normal Usage:
        .. code-block:: bash
                salt '*' win_updates.list_updates
        
        Find all critical updates list in detail:
        .. code-block:: bash
                salt '*' win_updates.list_updates categories=['Critical Updates'] verbose
        
        '''
        
        log.debug('categories to search for are: '.format(str(categories)))
        quidditch = PyWinUpdater()
        if categories:
                quidditch.SetCategories(categories)
        quidditch.SetIncludes(includes)
        
        
        ##this is where we be seeking the things! yar!
        comment, passed, retries = _search(quidditch,retries)
        if not passed:
                return (comment,str(passed))
        log.debug('verbose: {0}'.format(str(verbose)))
        if verbose:
                return str(quidditch.GetSearchResultsPretty())
        return str(quidditch)

def download_updates(includes=None,retries=5,categories=None):
        '''
        Downloads all available updates, skipping those that require user interaction.
        
        you can set the maximum number of retries to n in the search process by 
        adding: retries=n
        
        various aspects of the updates can be included or excluded. this feature is
        still indevelopment.
        
        You can also specify by category of update similarly to how you do includes:
        categories=['Windows 7','Security Updates']
        Some known categories:
                        Updates
                        Windows 7
                        Critical Updates
                        Security Updates
                        Update Rollups
        
        CLI Example:
        Normal Usage:
        .. code-block:: bash
                salt '*' win_updates.download_updates
        
        Find all critical updates list in detail:
        .. code-block:: bash
                salt '*' win_updates.download_updates categories=['Critical Updates'] verbose
        
        '''
        log.debug('categories to search for are: '.format(str(categories)))
        quidditch = PyWinUpdater()
        quidditch.SetCategories(categories)
        quidditch.SetIncludes(includes)
        
        
        ##this is where we be seeking the things! yar!
        comment, passed, retries = _search(quidditch,retries)
        if not passed:
                return (comment,str(passed))
        
        ##this is where we get all the things! i.e. download updates.
        comment, passed, retries = _download(quidditch,retries)
        if not passed:
                return (comment,str(passed))

        try:
                comment = quidditch.GetDownloadResults()
        except Exception as e:
                comment = 'could not get results, but updates were installed.'
        return 'Windows is up to date. \n{0}'.format(comment)

def install_updates(cached=None,includes=None,retries=5,categories=None):
        '''
        Downloads and installs all available updates, skipping those that require user interaction.
        
        Add 'cached' to only install those updates which have already been downloaded.
        
        you can set the maximum number of retries to n in the search process by 
        adding: retries=n
        
        various aspects of the updates can be included or excluded. this feature is
        still indevelopment.
        
        You can also specify by category of update similarly to how you do includes:
        categories=['Windows 7','Security Updates']
        Some known categories:
                        Updates
                        Windows 7
                        Critical Updates
                        Security Updates
                        Update Rollups
        
        CLI Example:
        Normal Usage:
        .. code-block:: bash
                salt '*' win_updates.install_updates
        
        Find all critical updates list in detail:
        .. code-block:: bash
                salt '*' win_updates.install_updates categories=['Critical Updates'] verbose
        
        '''
        
        log.debug('categories to search for are: '.format(str(categories)))
        quidditch = PyWinUpdater()
        quidditch.SetCategories(categories)
        quidditch.SetIncludes(includes)
        
        
        ##this is where we be seeking the things! yar!
        comment, passed, retries = _search(quidditch,retries)
        if not passed:
                return (comment,str(passed))
        
        ##this is where we get all the things! i.e. download updates.
        comment, passed, retries = _download(quidditch,retries)
        if not passed:
                return (comment,str(passed))

        ##this is where we put things in their place!
        comment, passed, retries = _install(quidditch,retries)
        if not passed:
                return (comment,str(passed))

        try:
                comment = quidditch.GetInstallationResultsPretty()
        except Exception as e:
                comment = 'could not get results, but updates were installed.'
        return 'Windows is up to date. \n{0}'.format(comment)
        
#To the King#
