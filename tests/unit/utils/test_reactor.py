# -*- coding: utf-8 -*-

from __future__ import absolute_import
import time
import shutil
import tempfile
import os

from contextlib import contextmanager

import salt.utils
from salt.utils.process import clean_proc
import salt.utils.reactor as reactor

from tests.integration import AdaptedConfigurationTestCaseMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock


@contextmanager
def reactor_process(opts, reactor):
    opts = dict(opts)
    opts['reactor'] = reactor
    proc = reactor.Reactor(opts)
    proc.start()
    try:
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(2)
        yield
    finally:
        clean_proc(proc)


def _args_sideffect(*args, **kwargs):
    return args, kwargs


@skipIf(True, 'Skipping until its clear what and how is this supposed to be testing')
class TestReactor(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.opts = self.get_temp_config('master')
        self.tempdir = tempfile.mkdtemp(dir=TMP)
        self.sls_name = os.path.join(self.tempdir, 'test.sls')
        with salt.utils.fopen(self.sls_name, 'w') as fh:
            fh.write('''
update_fileserver:
  runner.fileserver.update
''')

    def tearDown(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)
        del self.opts
        del self.tempdir
        del self.sls_name

    def test_basic(self):
        reactor_config = [
            {'salt/tagA': ['/srv/reactor/A.sls']},
            {'salt/tagB': ['/srv/reactor/B.sls']},
            {'*': ['/srv/reactor/all.sls']},
        ]
        wrap = reactor.ReactWrap(self.opts)
        with patch.object(reactor.ReactWrap, 'local', MagicMock(side_effect=_args_sideffect)):
            ret = wrap.run({'fun': 'test.ping',
                            'state': 'local',
                            'order': 1,
                            'name': 'foo_action',
                            '__id__': 'foo_action'})
            raise Exception(ret)
