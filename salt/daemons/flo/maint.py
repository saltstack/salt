# -*- coding: utf-8 -*-
'''
Define the behaviors used in the maintenance process
'''
from __future__ import absolute_import
# Import python libs
import os
import time
import logging
import multiprocessing

# Import ioflo libs
import ioflo.base.deeding

# Import salt libs
import salt.fileserver
import salt.loader
import salt.utils.minions
import salt.daemons.masterapi
import salt.daemons.flo

log = logging.getLogger(__name__)


@ioflo.base.deeding.deedify(
        'SaltRaetMaintFork',
        ioinits={'opts': '.salt.opts', 'proc_mgr': '.salt.usr.proc_mgr'})
def maint_fork(self):
    '''
    For off the maintinence process from the master router process
    FloScript:

    do salt raet maint fork at enter
    '''
    self.proc_mgr.value.add_process(Maintenance, args=(self.opts.value,))


class Maintenance(multiprocessing.Process):
    '''
    Start the maintinance process within ioflo
    '''
    def __init__(self, opts):
        super(Maintenance, self).__init__()
        self.opts = opts

    def run(self):
        '''
        Spin up a worker, do this in s multiprocess
        '''
        behaviors = ['salt.daemons.flo']
        preloads = [('.salt.opts', dict(value=self.opts))]
        preloads.extend(salt.daemons.flo.explode_opts(self.opts))

        console_logdir = self.opts.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, 'maintenance.log')
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name='maintenance',
                period=float(self.opts['loop_interval']),
                stamp=0.0,
                real=self.opts['ioflo_realtime'],
                filepath=self.opts['maintenance_floscript'],
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


class SaltRaetMaintSetup(ioflo.base.deeding.Deed):
    '''
    Init loader objects used
    FloScript:

    do salt raet maint setup at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'fileserver': '.salt.loader.fileserver',
               'runners': '.salt.loader.runners',
               'pillargitfs': '.salt.loader.pillargitfs',
               'ckminions': '.salt.loader.ckminions'}

    def action(self):
        '''
        Set up the objects used in the maint process
        '''
        self.fileserver.value = salt.fileserver.Fileserver(self.opts.value)
        self.runners.value = salt.loader.runner(self.opts.value)
        self.ckminions.value = salt.utils.minions.CkMinions(self.opts.value)
        self.pillargitfs.value = salt.daemons.masterapi.init_git_pillar(
                self.opts.value)


class SaltRaetMaintFileserverClean(ioflo.base.deeding.Deed):
    '''
    Clear the fileserver backend caches
    FloScript:

    do salt raet maint fileserver clean at enter

    '''
    Ioinits = {'opts': '.salt.opts'}

    def action(self):
        '''
        Clean!
        '''
        salt.daemons.masterapi.clean_fsbackend(self.opts.value)


class SaltRaetMaintOldJobsClear(ioflo.base.deeding.Deed):
    '''
    Iterate over the jobs directory and clean out the old jobs
    FloScript:

    do salt raet maint old jobs clear

    '''
    Ioinits = {'opts': '.salt.opts'}

    def action(self):
        '''
        Clear out the old jobs cache
        '''
        salt.daemons.masterapi.clean_old_jobs(self.opts.value)


class SaltRaetMaintBackendsUpdate(ioflo.base.deeding.Deed):
    '''
    Update the fileserver and external pillar caches
    FloScript:

    do salt raet maint backends update

    '''
    Ioinits = {'opts': '.salt.opts',
               'fileserver': '.salt.loader.fileserver',
               'pillargitfs': '.salt.loader.pillargitfs'}

    def action(self):
        '''
        Update!
        '''
        for pillargit in self.pillargitfs.value:
            pillargit.update()
        salt.daemons.masterapi.fileserver_update(self.fileserver.value)


class SaltZmqMaintRotate(ioflo.base.deeding.Deed):
    '''
    Update the zmq publish session key
    '''
    Ioinits = {'opts': '.salt.opts',
               'aes': '.salt.var.zmq.aes',
               'rotate': '.salt.var.zmq.rotate'}

    def action(self):
        '''
        Rotate the AES key rotation
        '''
        now = time.time()
        if not self.last_rotate.value:
            self.rotate.value = now
        to_rotate = False
        dfn = os.path.join(self.opts.value['cachedir'], '.dfn')
        try:
            stats = os.stat(dfn)
            if stats.st_mode == 0o100400:
                to_rotate = True
            os.remove(dfn)
        except os.error:
            pass

        if self.opts.value.get('publish_session'):
            if now - self.rotate.value >= self.opts['publish_session']:
                to_rotate = True

        if to_rotate:
            log.info('Rotating master AES key')
            # should be unecessary-- since no one else should be modifying
            with self.aes.value.get_lock():
                self.aes.value.value = salt.crypt.Crypticle.generate_key_string()
            #self.event.fire_event({'rotate_aes_key': True}, tag='key')
            self.rotate.value = now
            if self.opts.value.get('ping_on_rotate'):
                # Ping all minions to get them to pick up the new key
                log.debug('Pinging all connected minions '
                          'due to AES key rotation')
                salt.utils.master.ping_all_connected_minions(self.opts.value)
