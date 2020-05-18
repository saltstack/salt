# -*- coding: utf-8 -*-
"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""
from __future__ import absolute_import, print_function, unicode_literals

import copy
import os
import pathlib
import shutil
import tempfile

import salt.fileclient
import salt.fileserver.roots as roots
import salt.utils.files
import salt.utils.hashutils
import salt.utils.platform
from tests.support.mixins import (
    AdaptedConfigurationTestCaseMixin,
    LoaderModuleMockMixin,
)
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

UNICODE_FILENAME = "питон.txt"
UNICODE_DIRNAME = UNICODE_ENVNAME = "соль"


class RootsTest(TestCase, AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        self.opts = self.get_temp_config("master")
        empty_dir = os.path.join(RUNTIME_VARS.TMP_STATE_TREE, "empty_dir")
        if not os.path.isdir(empty_dir):
            os.makedirs(empty_dir)
        return {roots: {"__opts__": self.opts}}

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        full_path_to_file = os.path.join(RUNTIME_VARS.BASE_FILES, "testfile")
        shutil.copyfile(full_path_to_file, os.path.join(cls.tmp_dir, "testfile"))

    @classmethod
    def tearDownClass(cls):
        salt.utils.files.rm_rf(cls.tmp_dir)

    def tearDown(self):
        del self.opts

    def test_file_list(self):
        ret = roots.file_list({"saltenv": "base"})
        self.assertIn("testfile", ret)
        self.assertIn(UNICODE_FILENAME, ret)

    def test_find_file(self):
        ret = roots.find_file("testfile")
        self.assertEqual("testfile", ret["rel"])

        full_path_to_file = os.path.join(RUNTIME_VARS.BASE_FILES, "testfile")
        self.assertEqual(full_path_to_file, ret["path"])

    def test_serve_file(self):
        with patch.dict(roots.__opts__, {"file_buffer_size": 262144}):
            load = {
                "saltenv": "base",
                "path": os.path.join(self.tmp_dir, "testfile"),
                "loc": 0,
            }
            fnd = {"path": os.path.join(self.tmp_dir, "testfile"), "rel": "testfile"}
            ret = roots.serve_file(load, fnd)

            with salt.utils.files.fopen(
                os.path.join(RUNTIME_VARS.BASE_FILES, "testfile"), "rb"
            ) as fp_:
                data = fp_.read()

            self.assertDictEqual(ret, {"data": data, "dest": "testfile"})

    def test_envs(self):
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"][UNICODE_ENVNAME] = opts["file_roots"]["base"]
        with patch.dict(roots.__opts__, opts):
            ret = roots.envs()
        self.assertIn("base", ret)
        self.assertIn(UNICODE_ENVNAME, ret)

    def test_file_hash(self):
        load = {
            "saltenv": "base",
            "path": os.path.join(self.tmp_dir, "testfile"),
        }
        fnd = {"path": os.path.join(self.tmp_dir, "testfile"), "rel": "testfile"}
        ret = roots.file_hash(load, fnd)

        # Hashes are different in Windows. May be how git translates line
        # endings
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.BASE_FILES, "testfile"), "rb"
        ) as fp_:
            hsum = salt.utils.hashutils.sha256_digest(fp_.read())

        self.assertDictEqual(ret, {"hsum": hsum, "hash_type": "sha256"})

    def test_file_list_emptydirs(self):
        ret = roots.file_list_emptydirs({"saltenv": "base"})
        self.assertIn("empty_dir", ret)

    def test_file_list_with_slash(self):
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"]["foo/bar"] = opts["file_roots"]["base"]
        load = {
            "saltenv": "foo/bar",
        }
        with patch.dict(roots.__opts__, opts):
            ret = roots.file_list(load)
        self.assertIn("testfile", ret)
        self.assertIn(UNICODE_FILENAME, ret)

    def test_dir_list(self):
        ret = roots.dir_list({"saltenv": "base"})
        self.assertIn("empty_dir", ret)
        self.assertIn(UNICODE_DIRNAME, ret)

    def test_symlink_list(self):
        source_sym = pathlib.Path(RUNTIME_VARS.TMP_BASEENV_STATE_TREE) / "source_sym"
        source_sym.write_text("")
        dest_sym = pathlib.Path(RUNTIME_VARS.TMP_BASEENV_STATE_TREE) / "dest_sym"
        dest_sym.symlink_to(str(source_sym))
        self.addCleanup(dest_sym.unlink)
        self.addCleanup(source_sym.unlink)
        ret = roots.symlink_list({"saltenv": "base"})
        self.assertDictEqual(ret, {"dest_sym": str(source_sym)})

    def test_dynamic_file_roots(self):
        dyn_root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        top_sls = os.path.join(dyn_root_dir, "top.sls")
        with salt.utils.files.fopen(top_sls, "w") as fp_:
            fp_.write("{{saltenv}}:\n  '*':\n    - dynamo\n")
        dynamo_sls = os.path.join(dyn_root_dir, "dynamo.sls")
        with salt.utils.files.fopen(dynamo_sls, "w") as fp_:
            fp_.write("foo:\n  test.nop\n")
        opts = {"file_roots": copy.copy(self.opts["file_roots"])}
        opts["file_roots"]["__env__"] = [dyn_root_dir]
        with patch.dict(roots.__opts__, opts):
            ret1 = roots.find_file("dynamo.sls", "dyn")
            ret2 = roots.file_list({"saltenv": "dyn"})
        self.assertEqual("dynamo.sls", ret1["rel"])
        self.assertIn("top.sls", ret2)
        self.assertIn("dynamo.sls", ret2)
