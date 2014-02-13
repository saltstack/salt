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


@ioflo.base.deeding.deedify('master_keys', ioinits={'opts': '.salt.etc.opts', 'keys': '.salt.etc.keys.master'})
def master_keys(self):
    '''
    Return the master keys
    '''
    self.keys.value = salt.daemons.masterapi.master_keys(self.opts.value)


@ioflo.base.deeding.deedify('clean_old_jobs', ioinits={'opts': '.salt.etc.opts'})
def clean_old_jobs(self):
    '''
    Call the clan old jobs routine
    '''
    salt.daemons.masterapi.clean_old_jobs(self.opts.value)


@ioflo.base.deeding.deedify('access_keys', ioinits={'opts': '.salt.etc.opts'})
def access_keys(self):
    '''
    Build the access keys
    '''
    salt.daemons.masterapi.access_keys(self.opts.value)


@ioflo.base.deeding.deedify('fileserver_update', ioinits={'opts': '.salt.etc.opts'})
def fileserver_update(self):
    '''
    Update the fileserver backends
    '''
    salt.daemons.masterapi.fileserver_update(self.opts.value)


class RemoteMaster(ioflo.base.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.etc.opts',
               'ret_in': '.salt.net.ret_in',
               'ret_out': '.salt.net.ret_out'}

    def __init__(self):
        ioflo.base.deeding.deeding.Deed.__init__(self)

    def postioinit(self):
        '''
        Set up required objects
        '''
        self.remote = salt.daemons.masterapi.RemoteFuncs(self.opts.value)

    def action(self):
        '''
        Perform an action
        '''
        if self.ret_in.value:
            exchange = self.ret_in.value.pop()
            load = exchange.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return False
            if load['cmd'].startswith('__'):
                return False
            exchange['ret'] = getattr(self.remote, load['cmd'])(load)
            self.ret_out.value.append(exchange)


class LocalMaster(ioflo.base.deeding.Deed):
    '''
    Abstract access to the core salt master api
    '''
    Ioinits = {'opts': '.salt.etc.opts',
               'local_in': '.salt.net.local_in',
               'local_out': '.salt.net.local_out'}

    def __init__(self):
        ioflo.base.deeding.Deed.__init__(self)

    def postioinit(self):
        '''
        Set up required objects
        '''
        self.remote = salt.daemons.masterapi.LocalFuncs(self.opts.value)

    def action(self):
        '''
        Perform an action
        '''
        if self.local_in.value:
            exchange = self.local_in.value.pop()
            load = exchange.get('load')
            # If the load is invalid, just ignore the request
            if not 'cmd' in load:
                return False
            if load['cmd'].startswith('__'):
                return False
            exchange['ret'] = getattr(self.local, load['cmd'])(load)
            self.local_out.value.append(exchange)
