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
opts['caller_floscript']
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import modules
from . import core
from . import worker
from . import maint
from . import reactor
from . import zero
from . import jobber
from . import dummy

__all__ = ['core', 'worker', 'maint', 'zero', 'dummy', 'jobber', 'reactor']

# Import salt libs
import salt.daemons.masterapi
import salt.utils.stringutils
from salt.ext import six

# Import 3rd-party libs
import ioflo.app.run  # pylint: disable=3rd-party-module-not-gated


def explode_opts(opts):
    '''
    Explode the opts into a preloads list
    '''
    preloads = [(salt.utils.stringutils.to_str('.salt.opts'), dict(value=opts))]
    for key, val in six.iteritems(opts):
        ukey = key.replace('.', '_')
        preloads.append((salt.utils.stringutils.to_str('.salt.etc.{0}'.format(ukey)), dict(value=val)))
    preloads.append((salt.utils.stringutils.to_str('.salt.etc.id'), dict(value=opts['id'])))
    return preloads


def warn_deprecated():
    salt.utils.versions.warn_until(
        'Neon',
        'The \'raet\' transport has been deprecated and will be removed in '
        'Salt {version}. Please use \'zeromq\' or \'tcp\' transport instead.'
    )


class IofloMaster(object):
    '''
    IofloMaster Class
    '''
    def __init__(self, opts):
        '''
        Assign self.opts
        '''
        warn_deprecated()
        self.opts = opts
        self.preloads = explode_opts(self.opts)
        self.access_keys = salt.daemons.masterapi.access_keys(self.opts)
        self.preloads.append(
                (salt.utils.stringutils.to_str('.salt.access_keys'), dict(value=self.access_keys)))

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
        warn_deprecated()
        self.opts = opts
        self.restart = False

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

    def call_in(self, behaviors=None):
        '''
        Start up caller minion for salt-call when there is no local minion

        '''
        if behaviors is None:
            behaviors = []
        behaviors.extend(['salt.daemons.flo'])

        preloads = explode_opts(self.opts)

        console_logdir = self.opts.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, 'caller.log')
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name=self.opts['id'],
                period=float(self.opts['ioflo_period']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['caller_floscript'],
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
