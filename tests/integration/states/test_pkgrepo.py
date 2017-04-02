# -*- coding: utf-8 -*-
'''
tests for pkgrepo states
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains
)

# Import salt libs
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


class PkgrepoTest(integration.ModuleCase,
                  integration.SaltReturnAssertsMixin):
    '''
    pkgrepo state tests
    '''
    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    @requires_system_grains
    def test_pkgrepo_01_managed(self, grains):
        '''
        This is a destructive test as it adds a repository.
        '''
        os_grain = self.run_function('grains.item', ['os'])['os']
        os_release_info = tuple(self.run_function('grains.item', ['osrelease_info'])['osrelease_info'])
        if os_grain == 'Ubuntu' and os_release_info >= (15, 10):
            self.skipTest(
                'The PPA used for this test does not exist for Ubuntu Wily'
                ' (15.10) and later.'
            )

        if grains['os_family'] == 'Debian':
            try:
                from aptsources import sourceslist
            except ImportError:
                self.skipTest(
                    'aptsources.sourceslist python module not found'
                )
        ret = self.run_function('state.sls', mods='pkgrepo.managed', timeout=120)
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/managed.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in six.iteritems(ret):
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))

    @destructiveTest
    @skipIf(salt.utils.is_windows(), 'minion is windows')
    def test_pkgrepo_02_absent(self):
        '''
        This is a destructive test as it removes the repository added in the
        above test.
        '''
        os_grain = self.run_function('grains.item', ['os'])['os']
        os_release_info = tuple(self.run_function('grains.item', ['osrelease_info'])['osrelease_info'])
        if os_grain == 'Ubuntu' and os_release_info >= (15, 10):
            self.skipTest(
                'The PPA used for this test does not exist for Ubuntu Wily'
                ' (15.10) and later.'
            )

        ret = self.run_function('state.sls', mods='pkgrepo.absent', timeout=120)
        # If the below assert fails then no states were run, and the SLS in
        # tests/integration/files/file/base/pkgrepo/absent.sls needs to be
        # corrected.
        self.assertReturnNonEmptySaltType(ret)
        for state_id, state_result in six.iteritems(ret):
            self.assertSaltTrueReturn(dict([(state_id, state_result)]))
