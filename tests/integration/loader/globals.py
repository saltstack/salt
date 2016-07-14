# -*- coding: utf-8 -*-
'''
    integration.loader.globals
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding globals that it should pack in
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.loader
import inspect
import yaml

# Import 3rd-party libs
import salt.ext.six as six


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
        global_vars = []
        for val in six.itervalues(mod_dict):
            # only find salty globals
            if val.__module__.startswith('salt.loaded') and hasattr(val, '__globals__'):
                global_vars.append(val.__globals__)

        # if we couldn't find any, then we have no modules -- so something is broken
        self.assertNotEqual(global_vars, [], msg='No modules were loaded.')

        # get the names of the globals you should have
        func_name = inspect.stack()[1][3]
        names = next(six.itervalues(yaml.load(getattr(self, func_name).__doc__)))

        # Now, test each module!
        for item in global_vars:
            for name in names:
                self.assertIn(name, list(item.keys()))

    def test_auth(self):
        '''
        Test that auth mods have:
            - __pillar__
            - __grains__
            - __salt__
            - __context__
        '''
        self._verify_globals(salt.loader.auth(self.master_opts))

    def test_runners(self):
        '''
        Test that runners have:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
            - __context__
        '''
        self._verify_globals(salt.loader.runner(self.master_opts))

    def test_returners(self):
        '''
        Test that returners have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
            - __context__
        '''
        self._verify_globals(salt.loader.returners(self.master_opts, {}))

    def test_pillars(self):
        '''
        Test that pillars have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
            - __context__
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
            - __context__
        '''
        self._verify_globals(salt.loader.outputters(self.master_opts))

    def test_serializers(self):
        '''
        Test that serializers have: []
        '''
        self._verify_globals(salt.loader.serializers(self.master_opts))

    def test_states(self):
        '''
        Test that states:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
            - __context__
        '''
        self._verify_globals(salt.loader.states(self.master_opts, {}, {}))

    def test_renderers(self):
        '''
        Test that renderers have:
            - __salt__    # Execution functions (i.e. __salt__['test.echo']('foo'))
            - __grains__  # Grains (i.e. __grains__['os'])
            - __pillar__  # Pillar data (i.e. __pillar__['foo'])
            - __opts__    # Minion configuration options
            - __context__ # Context dict shared amongst all modules of the same type
        '''
        self._verify_globals(salt.loader.render(self.master_opts, {}))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderGlobalsTest, needs_daemon=False)
