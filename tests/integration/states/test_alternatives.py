# -*- coding: utf-8 -*-
'''
Integration tests for the alternatives state module
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

NO_ALTERNATIVES = False
if not os.path.exists('/etc/alternatives'):
    NO_ALTERNATIVES = True


@skipIf(NO_ALTERNATIVES, '/etc/alternatives does not exist on the system')
class AlterantivesStateTest(ModuleCase, SaltReturnAssertsMixin):
    @destructiveTest
    def test_install_set_and_remove(self):
        ret = self.run_state('alternatives.set', name='alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertSaltFalseReturn(ret)

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH, priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, RUNTIME_VARS.SHELL_TRUE_PATH, keys=['path'])

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH, priority=50)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.install', name='alt-test',
            link='/usr/local/bin/alt-test', path=RUNTIME_VARS.SHELL_FALSE_PATH, priority=90)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, RUNTIME_VARS.SHELL_FALSE_PATH, keys=['path'])

        ret = self.run_state('alternatives.set', name='alt-test', path=RUNTIME_VARS.SHELL_FALSE_PATH)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.set', name='alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, RUNTIME_VARS.SHELL_TRUE_PATH, keys=['path'])

        ret = self.run_state('alternatives.set', name='alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, {})

        ret = self.run_state('alternatives.remove', name='alt-test', path=RUNTIME_VARS.SHELL_TRUE_PATH)
        self.assertSaltTrueReturn(ret)

        ret = self.run_state('alternatives.remove', name='alt-test', path=RUNTIME_VARS.SHELL_FALSE_PATH)
        self.assertSaltTrueReturn(ret)
