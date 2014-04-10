'''
Define the behaviors used in the maintinance process
'''
# Import ioflo libs
import ioflo.base.deeding

# Import salt libs
import salt.fileserver
import salt.loader
import salt.utils.minions
import salt.daemons.masterapi


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
