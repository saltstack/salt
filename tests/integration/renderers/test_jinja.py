# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import os

import salt.utils.files

from tests.support.case import ModuleCase, ShellCase
from tests.support.helpers import with_tempdir


class JinjaRendererTest(ModuleCase):

    @with_tempdir()
    def test_issue_54765(self, tmpdir):
        file_path = os.path.join(tmpdir, 'issue-54765')
        ret = self.run_function('state.sls', mods='issue-54765', pillar={'file_path': file_path})
        key = 'file_|-issue-54765_|-{}_|-managed'.format(file_path)
        assert key in ret
        assert ret[key]['result'] is True
        with salt.utils.files.fopen(file_path, 'r') as fp:
            assert fp.read().strip() == 'bar'


class JinjaRenderCallTest(ShellCase):

    @with_tempdir()
    def test_issue_54765(self, tmpdir):
        file_path = os.path.join(tmpdir, 'issue-54765')
        pillar_str = '\'{{"file_path": "{}"}}\''.format(file_path)
        ret = self.run_call('state.apply issue-54765 pillar={}'.format(pillar_str), local=True)
        assert '      Result: True' in ret
        with salt.utils.files.fopen(file_path, 'r') as fp:
            assert fp.read().strip() == 'bar'
