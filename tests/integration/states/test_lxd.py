# -*- coding: utf-8 -*-
'''
Integration tests for the lxd states
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt utils
import salt.utils.path

# Import Salt Testing Libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.mixins import SaltReturnAssertsMixin

import pytest
try:
    import pylxd  # pylint: disable=import-error,unused-import
    HAS_PYLXD = True
except ImportError:
    HAS_PYLXD = False


@pytest.mark.destructive_test
@skipIf(not salt.utils.path.which('lxd'), 'LXD not installed')
@skipIf(not salt.utils.path.which('lxc'), 'LXC not installed')
@skipIf(not HAS_PYLXD, 'pylxd not installed')
class LxdTestCase(ModuleCase, SaltReturnAssertsMixin):

    run_once = False

    @flaky
    def test_01__init_lxd(self):
        if LxdTestCase.run_once:
            return
        ret = self.run_state('lxd.init', name='foobar')
        self.assertSaltTrueReturn(ret)
        LxdTestCase.run_once = True
        name = 'lxd_|-foobar_|-foobar_|-init'
        assert name in ret
        assert ret[name]['storage_backend'] == 'dir'
