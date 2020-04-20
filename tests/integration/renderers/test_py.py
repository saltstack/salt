# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.utils.files
from tests.support.case import ModuleCase
from tests.support.helpers import with_tempdir


class PyJinjaRendererTest(ModuleCase):
    @with_tempdir()
    def test_issue_55390(self, tmpdir):
        file_path = os.path.join(tmpdir, "issue-55390")
        templatesrc = "salt://issue-55390/code.py"

        # the sls file here is rendered with jinja|py,
        # which then uses file.managed with template=py
        # to create our output file
        ret = self.run_function(
            "state.sls",
            mods="issue-55390",
            pillar={"file_path": file_path, "source_path": templatesrc},
        )
        key = "file_|-issue-55390_|-{}_|-managed".format(file_path)
        assert key in ret

        assert ret[key]["result"] is True

        with salt.utils.files.fopen(file_path, "r") as fp:
            assert fp.read().strip() == "lol"
