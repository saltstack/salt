# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, unicode_literals
import logging


# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
import salt.modules.cmdmod
import salt.utils.platform

log = logging.getLogger(__name__)


@skipIf(not salt.utils.path.which('bash'), 'Bash needed for this test')
class VendorTornadoTest(TestCase):
    '''
    Ensure we are no using any non vendor'ed tornado
    '''

    def test_vendored_tornado_import(self):
        grep_call = salt.modules.cmdmod.run_stdout(
            cmd='bash -c \'grep -r "import tornado" ./salt/*\'',
            cwd=RUNTIME_VARS.CODE_DIR,
            ignore_retcode=True,
        ).split('\n')
        valid_lines = []
        for line in grep_call:
            if line == '':
                continue
            # Skip salt/ext/tornado/.. since there are a bunch of imports like
            # this in docstrings.
            if 'salt/ext/tornado/' in line:
                continue
            log.error("Test found bad line: %s", line)
            valid_lines.append(line)
        assert valid_lines == [], len(valid_lines)

    def test_vendored_tornado_import_from(self):
        grep_call = salt.modules.cmdmod.run_stdout(
            cmd='bash -c \'grep -r "from tornado" ./salt/*\'',
            cwd=RUNTIME_VARS.CODE_DIR,
            ignore_retcode=True,
        ).split('\n')
        valid_lines = []
        for line in grep_call:
            if line == '':
                continue
            log.error("Test found bad line: %s", line)
            valid_lines.append(line)
        assert valid_lines == [], len(valid_lines)
