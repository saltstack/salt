# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import errno
import logging
import os
import re
import shutil
import signal
import tempfile
import time
import textwrap
import threading

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase
from tests.support.helpers import flaky, expensiveTest
from tests.support.mock import MagicMock, patch
from tests.support.unit import skipIf

# Import Salt Libs
import salt.exceptions
import salt.utils.platform
import salt.utils.event
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import queue

log = logging.getLogger(__name__)


class SyncRunnerTest(ShellCase):
    '''
    Test the sync runner.
    '''
    def test_sync_auth_includes_auth(self):
        '''
        '''
        ret_output = self.run_run('saltutil.sync_auth')
        assert '- auth.nullauth' in [ret_entry.strip() for ret_entry in ret_output]
        # Clean up?
        os.unlink(os.path.join(self.master_opts['root_dir'], 'extension_modules', 'auth', 'nullauth.py'))

    def test_sync_all_includes_auth(self):
        '''
        '''
        ret_output = self.run_run('saltutil.sync_all')
        assert '- auth.nullauth' in [ret_entry.strip() for ret_entry in ret_output]
        # Clean up?
        os.unlink(os.path.join(self.master_opts['root_dir'], 'extension_modules', 'auth', 'nullauth.py'))
