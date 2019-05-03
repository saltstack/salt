# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import uuid
import hashlib
import logging
import psutil
import shutil
import signal
import tempfile
import textwrap

# Import Salt Testing libs
from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import (
    flaky,
    get_unused_localhost_port,
    skip_if_not_root,
    with_tempfile)
from tests.support.unit import skipIf
import tests.support.paths as paths

# Import 3rd party libs
import salt.ext.six as six

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

log = logging.getLogger(__name__)

import pprint

class ExecutorTest(ModuleCase, ShellCase):

    def setup(self):
        self.run_function('saltutil.sync_all')

    def test_executor(self):
        '''
        test that dunders are set
        '''
        data = self.run_call('test.arg --module-executors=arg')
        pprint.pprint(data)
