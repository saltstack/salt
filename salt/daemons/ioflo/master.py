# -*- coding: utf-8 -*-
'''
The behaviors to run the salt master via ioflo
'''

# Import python libs
#import collections

# Import salt libs
import salt.daemons.masterapi

# Import ioflo libs
import ioflo.base.deeding
from ioflo.base.odicting import odict


@ioflo.base.deeding.deedify('master_keys', parametric=True)
def master_keys(self, **kwargs):
    '''
    Return the master keys
    '''
    salt.daemons.masterapi.master_keys(kwargs.get('opts'))


@ioflo.base.deeding.deedify('clean_old_jobs', parametric=True)
def clean_old_jobs(self, **kwargs):
    '''
    Call the clan old jobs routine
    '''
    salt.daemons.masterapi.clean_old_jobs(kwargs.get('opts'))


@ioflo.base.deeding.deedify('access_keys', parametric=True)
def access_keys(self, **kwargs):
    '''
    Build the access keys
    '''
    salt.daemons.masterapi.access_keys(kwargs.get('opts'))


@ioflo.base.deeding.deedify('fileserver_update', parametric=True)
def fileserver_update(self, **kwargs):
    '''
    Update the fileserver backends
    '''
    salt.daemons.masterapi.fileserver_update(kwargs.get('opts'))


class MasterRemoteDeed(ioflo.base.deeding.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinit = odict(opts='.opts')
    def __init__(self):
        ioflo.base.deeding.deeding.Deed.__init__(self)
        self.remote = salt.masterapi.RemoteFuncs(self.opts)

    def action(self, load):  # Not sure where the load is coming from quite yet
        '''
        Perform an action
        '''
        if not 'cmd' in load:
            return False
        if load['cmd'].startswith('__'):
            return False
        ret = getattr(self.remote, load['cmd'])(load)
        return ret  # Change top insert onto the return queue


class MasterLocalDeed(ioflo.base.deeding.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinit = odict(opts='.opts')
    def __init__(self):
        ioflo.base.deeding.deeding.Deed.__init__(self)
        self.local = salt.masterapi.LocalFuncs(self.opts)

    def action(self, load):  # Not sure where the load is coming from quite yet
        '''
        Perform an action
        '''
        if not 'cmd' in load:
            return False
        if load['cmd'].startswith('__'):
            return False
        ret = getattr(self.local, load['cmd'])(load)
        return ret  # Change top insert onto the return queue
