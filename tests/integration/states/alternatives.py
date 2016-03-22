# -*- coding: utf-8 -*-
'''
Integration tests for the alternatives state module
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import destructiveTest, ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class AlterantivesStateTest(integration.ModuleCase,
                            integration.SaltReturnAssertsMixIn):
    @destructiveTest
    def test_install_set_and_remove(self):
        ret = self.run_state('alternatives.set', name='alt-test', path='/bin/true')
        self.assertSaltFalseReturn(ret)

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path='/bin/true', priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, '/bin/true', keys=['path'])

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path='/bin/true', priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path='/bin/false', priority=90)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, '/bin/false', keys=['path'])

        ret = self.run_state('alternatives.set', name='alt-test', path='/bin/false')
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.set', name='alt-test', path='/bin/true')
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, '/bin/true', keys=['path'])

        ret = self.run_state('alternatives.set', name='alt-test', path='/bin/true')
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.remove', name='alt-test', path='/bin/true')
        self.assertSaltTrueReturn(ret)

        ret = self.run_state('alternatives.remove', name='alt-test', path='/bin/false')
        self.assertSaltTrueReturn(ret)
