# -*- coding: utf-8 -*-

from __future__ import absolute_import
import time
import shutil
import tempfile
import os

from contextlib import contextmanager

import tests.integration as integration

from salt.utils.process import clean_proc
from salt.utils import event

from tests.support.mock import patch


@contextmanager
def reactor_process(opts, reactor):
    opts = dict(opts)
    opts['reactor'] = reactor
    proc = event.Reactor(opts)
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


@contextmanager
def _args_sideffect(*args, **kwargs):
    return args, kwargs


class TestReactor(integration.ModuleCase):
    def setUp(self):
        self.opts = self.get_config('master', from_scratch=True)
        self.tempdir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        self.sls_name = os.path.join(self.tempdir, 'test.sls')
        with open(self.sls_name, 'w') as fh:
            fh.write('''
update_fileserver:
  runner.fileserver.update
''')

    def tearDown(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

    def test_basic(self):
        reactor_config = [
            {'salt/tagA': ['/srv/reactor/A.sls']},
            {'salt/tagB': ['/srv/reactor/B.sls']},
            {'*': ['/srv/reactor/all.sls']},
        ]
        wrap = event.ReactWrap(self.opts)
        with patch('salt.utils.event.ReactWrap.local', _args_sideffect):
            ret = wrap.run({'fun': 'test.ping',
                          'state': 'local',
                          'order': 1,
                          'name': 'foo_action',
                          '__id__': 'foo_action'})
            raise Exception(ret)
