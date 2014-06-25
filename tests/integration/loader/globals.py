# -*- coding: utf-8 -*-
'''
    integration.loader.globals
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding globals that it should pack in
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import integration
import salt.loader
import inspect
import yaml


class LoaderGlobalsTest(integration.ModuleCase):
    '''
    Test all of the globals that the loader is responsible for adding to modules

    This shouldn't be done here, but should rather be done per module type (in the cases where they are used)
    so they can check ALL globals that they have (or should have) access to.

    This is intended as a shorter term way of testing these so we don't break the loader
    '''
    def _verify_globals(self, mod_dict):
        '''
        Verify that the globals listed in the doc string (from the test) are in these modules
        '''
        # find the globals
        global_vars = None
        for val in mod_dict.itervalues():
            if hasattr(val, '__globals__'):
                global_vars = val.__globals__
                break
        # if we couldn't find any, then we have no modules-- so something is broken
        if global_vars is None:
            # TODO: log or something? Skip however we do that
            return

        # get the names of the globals you should have
        func_name = inspect.stack()[1][3]
        names = yaml.load(getattr(self, func_name).__doc__).values()[0]

        for name in names:
            assert name in global_vars

    def test_auth(self):
        '''
        Test that auth mods have:
            - __pillar__
            - __grains__
            - __salt__
        '''
        self._verify_globals(salt.loader.auth(self.master_opts))

    def test_runners(self):
        '''
        Test that runners have:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
        '''
        self._verify_globals(salt.loader.runner(self.master_opts))

    def test_returners(self):
        '''
        Test that returners have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
        '''
        self._verify_globals(salt.loader.returners(self.master_opts, {}))

    def test_pillars(self):
        '''
        Test that pillars have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
        '''
        self._verify_globals(salt.loader.pillars(self.master_opts, {}))

    def test_tops(self):
        '''
        Test that tops have: []
        '''
        self._verify_globals(salt.loader.tops(self.master_opts))

    def test_outputters(self):
        '''
        Test that outputters have:
            - __opts__
            - __pillar__
            - __grains__
        '''
        self._verify_globals(salt.loader.outputters(self.master_opts))

    def test_states(self):
        '''
        Test that states:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
        '''
        self._verify_globals(salt.loader.states(self.master_opts, {}))

    def test_log_handlers(self):
        '''
        Test that log_handlers have:
            - __path__
        '''
        self._verify_globals(salt.loader.log_handlers(self.master_opts))

    def test_renderers(self):
        '''
        Test that renderers have:
            - __salt__  # Execution functions (i.e. __salt__['test.echo']('foo'))
            - __grains__ # Grains (i.e. __grains__['os'])
            - __pillar__ # Pillar data (i.e. __pillar__['foo'])
            - __opts__ # Minion configuration options
        '''
        self._verify_globals(salt.loader.render(self.master_opts, {}))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderGlobalsTest, needs_daemon=False)
