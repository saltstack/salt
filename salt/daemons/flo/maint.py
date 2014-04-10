'''
Define the behaviors used in the maintinance process
'''
# Import python libs
import multiprocessing

# Import ioflo libs
import ioflo.base.deeding

# Import salt libs
import salt.fileserver
import salt.loader
import salt.utils.minions
import salt.daemons.masterapi


class MaintFork(ioflo.base.deeding.Deed):
    '''
    For off the maintinence process from the master router process
    '''
    Ioinits = {'opts': '.salt.opts'}

    def _fork_maint(self):
        '''
        Run the multiprocessing in here to fork the maintinace process
        '''
        proc = multiprocessing.Process(target=self._maint)
        proc.start()

    def _maint(self):
        '''
        Spin up a worker, do this in s multiprocess
        '''
        behaviors = ['salt.daemons.flo']
        preloads = [('.salt.opts', dict(value=self.opts.value))]
        ioflo.app.run.start(
                name='maintiance',
                period=float(self.opts.value['ioflo_period']),
                stamp=0.0,
                real=self.opts.value['ioflo_realtime'],
                filepath=self.opts.value['maintinance_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts.value['ioflo_verbose']),
                )

    def action(self):
        '''
        make go!
        '''
        self._fork_maint()


class MaintSetup(ioflo.base.deeding.Deed):
    '''
    Init loader objects used
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


class CleanFileserver(ioflo.base.deeding.Deed):
    '''
    Clear the fileserver backend caches
    '''
    Ioinits = {'opts': '.salt.opts'}

    def action(self):
        '''
        Clean!
        '''
        self.daemons.masterapi.clean_fsbackend(self.opts.value)


class JobsOldClear(ioflo.base.deeding.Deed):
    '''
    Iterate over the jobs directory and clean out the old jobs
    '''
    Ioinits = {'opts': '.salt.opts'}

    def action(self):
        '''
        Clear out the old jobs cache
        '''
        salt.daemons.masterapi.clean_old_jobs(self.opts.value)


class BackendsUpdate(ioflo.base.deeding.Deed):
    '''
    Update the fileserver and external pillar caches
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
