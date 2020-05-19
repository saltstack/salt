# -*- coding: utf-8 -*-
"""
Tests for the fileserver runner
"""
from __future__ import absolute_import, print_function, unicode_literals

import contextlib
import pathlib

import pytest
from tests.support.case import ShellCase
from tests.support.helpers import slowTest
from tests.support.runtests import RUNTIME_VARS


@pytest.mark.windows_whitelisted
class FileserverTest(ShellCase):
    """
    Test the fileserver runner
    """

    @slowTest
    def test_dir_list(self):
        """
        fileserver.dir_list
        """
        ret = self.run_run_plus(fun="fileserver.dir_list")
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("_modules" in ret["return"])

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.dir_list", backend="roots")
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("_modules" in ret["return"])

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.dir_list", backend=["roots"])
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("_modules" in ret["return"])

    @slowTest
    def test_empty_dir_list(self):
        """
        fileserver.empty_dir_list
        """
        ret = self.run_run_plus(fun="fileserver.empty_dir_list")
        self.assertIsInstance(ret["return"], list)
        self.assertEqual(ret["return"], [])

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.empty_dir_list", backend="roots")
        self.assertIsInstance(ret["return"], list)
        self.assertEqual(ret["return"], [])

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.empty_dir_list", backend=["roots"])
        self.assertIsInstance(ret["return"], list)
        self.assertEqual(ret["return"], [])

    @slowTest
    def test_envs(self):
        """
        fileserver.envs
        """
        ret = self.run_run_plus(fun="fileserver.envs")
        self.assertIsInstance(ret["return"], list)

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.envs", backend="roots")
        self.assertIsInstance(ret["return"], list)

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.envs", backend=["roots"])
        self.assertIsInstance(ret["return"], list)

    @slowTest
    def test_clear_file_list_cache(self):
        """
        fileserver.clear_file_list_cache

        If this test fails, then something may have changed in the test suite
        and we may have more than just "roots" configured in the fileserver
        backends. This assert will need to be updated accordingly.
        """
        saltenvs = sorted(self.run_run_plus(fun="fileserver.envs")["return"])

        @contextlib.contextmanager
        def gen_cache():
            """
            Create file_list cache so we have something to clear
            """
            for saltenv in saltenvs:
                self.run_run_plus(fun="fileserver.file_list", saltenv=saltenv)
            yield

        # Test with no arguments
        with gen_cache():
            ret = self.run_run_plus(fun="fileserver.clear_file_list_cache")
            ret["return"]["roots"].sort()
            self.assertEqual(ret["return"], {"roots": saltenvs})

        # Test with backend passed as string
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", backend="roots"
            )
            ret["return"]["roots"].sort()
            self.assertEqual(ret["return"], {"roots": saltenvs})

        # Test with backend passed as list
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", backend=["roots"]
            )
            ret["return"]["roots"].sort()
            self.assertEqual(ret["return"], {"roots": saltenvs})

        # Test with backend passed as string, but with a nonsense backend
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", backend="notarealbackend"
            )
            self.assertEqual(ret["return"], {})

        # Test with saltenv passed as string
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", saltenv="base"
            )
            self.assertEqual(ret["return"], {"roots": ["base"]})

        # Test with saltenv passed as list
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", saltenv=["base"]
            )
            self.assertEqual(ret["return"], {"roots": ["base"]})

        # Test with saltenv passed as string, but with a nonsense saltenv
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", saltenv="notarealsaltenv"
            )
            self.assertEqual(ret["return"], {})

        # Test with both backend and saltenv passed
        with gen_cache():
            ret = self.run_run_plus(
                fun="fileserver.clear_file_list_cache", backend="roots", saltenv="base"
            )
            self.assertEqual(ret["return"], {"roots": ["base"]})

    @slowTest
    def test_file_list(self):
        """
        fileserver.file_list
        """
        ret = self.run_run_plus(fun="fileserver.file_list")
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("grail/scene33" in ret["return"])

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.file_list", backend="roots")
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("grail/scene33" in ret["return"])

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.file_list", backend=["roots"])
        self.assertIsInstance(ret["return"], list)
        self.assertTrue("grail/scene33" in ret["return"])

    @slowTest
    def test_symlink_list(self):
        """
        fileserver.symlink_list
        """
        source_sym = pathlib.Path(RUNTIME_VARS.TMP_BASEENV_STATE_TREE) / "source_sym_1"
        source_sym.write_text("")
        dest_sym = pathlib.Path(RUNTIME_VARS.TMP_BASEENV_STATE_TREE) / "dest_sym_1"
        dest_sym.symlink_to(str(source_sym))
        self.addCleanup(dest_sym.unlink)
        self.addCleanup(source_sym.unlink)

        ret = self.run_run_plus(fun="fileserver.symlink_list")
        self.assertIsInstance(ret["return"], dict)
        self.assertTrue("dest_sym_1" in ret["return"])

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.symlink_list", backend="roots")
        self.assertIsInstance(ret["return"], dict)
        self.assertTrue("dest_sym_1" in ret["return"])

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.symlink_list", backend=["roots"])
        self.assertIsInstance(ret["return"], dict)
        self.assertTrue("dest_sym_1" in ret["return"])

    @slowTest
    def test_update(self):
        """
        fileserver.update
        """
        ret = self.run_run_plus(fun="fileserver.update")
        self.assertTrue(ret["return"])

        # Backend submitted as a string
        ret = self.run_run_plus(fun="fileserver.update", backend="roots")
        self.assertTrue(ret["return"])

        # Backend submitted as a list
        ret = self.run_run_plus(fun="fileserver.update", backend=["roots"])
        self.assertTrue(ret["return"])
