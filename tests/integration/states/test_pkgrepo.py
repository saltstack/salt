# -*- coding: utf-8 -*-
'''
tests for pkgrepo states
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains
)

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext import six


@destructiveTest
@skipIf(salt.utils.platform.is_windows(), 'minion is windows')
class PkgrepoTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    pkgrepo state tests
    '''
    @requires_system_grains
    def test_pkgrepo_01_managed(self, grains):
        '''
        Test adding a repo
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

    def test_pkgrepo_02_absent(self):
        '''
        Test removing the repo from the above test
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

    @requires_system_grains
    def test_pkgrepo_03_with_comments(self, grains):
        '''
        Test adding a repo with comments
        '''
        os_family = grains['os_family'].lower()

        if os_family in ('redhat',):
            kwargs = {
                'name': 'examplerepo',
                'baseurl': 'http://example.com/repo',
                'enabled': False,
                'comments': ['This is a comment']
            }
        elif os_family in ('debian',):
            self.skipTest('Debian/Ubuntu test case needed')
        else:
            self.skipTest("No test case for os_family '{0}'".format(os_family))

        try:
            # Run the state to add the repo
            ret = self.run_state('pkgrepo.managed', **kwargs)
            self.assertSaltTrueReturn(ret)

            # Run again with modified comments
            kwargs['comments'].append('This is another comment')
            ret = self.run_state('pkgrepo.managed', **kwargs)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertEqual(
                ret['changes'],
                {
                    'comments': {
                        'old': ['This is a comment'],
                        'new': ['This is a comment',
                                'This is another comment']
                    }
                }
            )

            # Run a third time, no changes should be made
            ret = self.run_state('pkgrepo.managed', **kwargs)
            self.assertSaltTrueReturn(ret)
            ret = ret[next(iter(ret))]
            self.assertFalse(ret['changes'])
            self.assertEqual(
                ret['comment'],
                "Package repo '{0}' already configured".format(kwargs['name'])
            )
        finally:
            # Clean up
            self.run_state('pkgrepo.absent', name=kwargs['name'])
