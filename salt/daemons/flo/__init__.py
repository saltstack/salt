# -*- coding: utf-8 -*-
'''
Package for ioflo and raet based daemons and associated ioflo behaviors

To use set
opts['transport'] ='raet'
master minion config
transport: raet

See salt.config.py for relevant defaults

opts['raet_port']
opts['master_floscript']
opts['minion_floscript']
opts['ioflo_period']
opts['ioflo_realtime']
opts['ioflo_verbose']
'''
import os

# Import modules
from . import core
from . import worker
from . import maint

__all__ = ['core', 'worker', 'maint']

# Import salt libs
import salt.daemons.masterapi

# Import ioflo libs
import ioflo.app.run


def explode_opts(opts):
    '''
    Explode the opts into a preloads list
    '''
    preloads = [('.salt.opts', dict(value=opts))]
    for key, val in opts.items():
        ukey = key.replace('.', '_')
        preloads.append(('.salt.etc.{0}'.format(ukey), dict(value=val)))
    return preloads


class IofloMaster(object):
    '''
    IofloMaster Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        self.opts = opts
        self.preloads = explode_opts(self.opts)
        self.access_keys = salt.daemons.masterapi.access_keys(self.opts)
        self.preloads.append(
                ('.salt.access_keys', dict(value=self.access_keys)))

    def start(self, behaviors=None):
        '''
        Start up ioflo

        port = self.opts['raet_port']
        '''
        if behaviors is None:
            behaviors = []
        behaviors.extend(['salt.daemons.flo'])

        console_logdir = self.opts.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, 'master.log')
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name='master',
                period=float(self.opts['ioflo_period']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['master_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=self.preloads,
                verbose=int(self.opts['ioflo_verbose']),
                consolepath=consolepath,
                )


class IofloMinion(object):
    '''
    IofloMinion Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        self.opts = opts

    def tune_in(self, behaviors=None):
        '''
        Start up ioflo

        port = self.opts['raet_port']
        '''
        if behaviors is None:
            behaviors = []
        behaviors.extend(['salt.daemons.flo'])

        preloads = explode_opts(self.opts)

        console_logdir = self.opts.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, 'minion.log')
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name=self.opts['id'],
                period=float(self.opts['ioflo_period']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['minion_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts['ioflo_verbose']),
                consolepath=consolepath,
                )

    start = tune_in  # alias
