# -*- coding: utf-8 -*-
'''
Integration tests for the alternatives state module
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration

NO_ALTERNATIVES = False
if not os.path.exists('/etc/alternatives'):
    NO_ALTERNATIVES = True


@skipIf(NO_ALTERNATIVES, '/etc/alternatives does not exist on the system')
class AlterantivesStateTest(integration.ModuleCase,
                            integration.SaltReturnAssertsMixIn):
    @destructiveTest
    def test_install_set_and_remove(self):
        name = 'alt-test'
        true_path = '/bin/true'
        false_path = '/bin/false'

        ret = self.run_state('alternatives.set', name=name, path=true_path)

        if ret['result'] is True and 'already set to' in ret['comment']:
            self.skipTest('{0} is already set to {1}. Skipping.'.format(name, true_path))

        self.assertSaltFalseReturn(ret)

        ret = self.run_state('alternatives.install', name=name,
            link='/usr/local/bin/alt-test', path=true_path, priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, true_path, keys=['path'])

        ret = self.run_state('alternatives.install', name=name,
            link='/usr/local/bin/alt-test', path=true_path, priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.install', name=name,
            link='/usr/local/bin/alt-test', path=false_path, priority=90)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, false_path, keys=['path'])

        ret = self.run_state('alternatives.set', name=name, path=false_path)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.set', name=name, path=true_path)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, true_path, keys=['path'])

        ret = self.run_state('alternatives.set', name=name, path=true_path)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.remove', name=name, path=true_path)
        self.assertSaltTrueReturn(ret)

        ret = self.run_state('alternatives.remove', name=name, path=false_path)
        self.assertSaltTrueReturn(ret)
