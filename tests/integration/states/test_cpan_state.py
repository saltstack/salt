# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.states.pip_state
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import os
import glob
import shutil
import sys

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains,
    with_system_user,
    skip_if_not_root,
    with_tempdir,
    patched_environ
)
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.versions
import salt.utils.win_dacl
import salt.utils.win_functions
import salt.utils.win_runas
import salt.modules.cpan as cpan
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six



class CpanStateTest(ModuleCase, SaltReturnAssertsMixin):

    @skip_if_not_root
    def test_cpan_installed_removed(self):
        '''
        Tests installed and removed states
        '''
        name = 'Template::Alloy'
        if "not installed" not in self.run_function('cpan.show', (name,))["installed version"]:
            # For now this is not implemented as state because it is experimental/non-stable
            # self.run_state('cpan.removed', name=name)
            self.run_function('cpan.remove', (name,))

        ret = self.run_state('cpan.installed', name=name)
        self.assertSaltTrueReturn(ret)

        # For now this is not implemented as state because it is experimental/non-stable
        # self.run_state('cpan.removed', name=name)
        self.run_function('cpan.remove', module=(name,))


