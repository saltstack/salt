# coding: utf-8

# Import Python libs
from __future__ import absolute_import

import os
import shutil
import tempfile

import salt.config
import salt.spm
import salt.utils.files
from tests.support.helpers import destructiveTest
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.mock import MagicMock, patch

# Import Salt Testing libs
from tests.support.unit import TestCase

_F1 = {
    "definition": {
        "name": "formula1",
        "version": "1.2",
        "release": "2",
        "summary": "test",
        "description": "testing, nothing to see here",
    }
}

_F1["contents"] = (
    (
        "FORMULA",
        (
            "name: {name}\n"
            "version: {version}\n"
            "release: {release}\n"
            "summary: {summary}\n"
            "description: {description}"
        ).format(**_F1["definition"]),
    ),
    ("modules/mod1.py", "# mod1.py"),
    ("modules/mod2.py", "# mod2.py"),
    ("states/state1.sls", "# state1.sls"),
    ("states/state2.sls", "# state2.sls"),
)


@destructiveTest
class SPMTestUserInterface(salt.spm.SPMUserInterface):
    """
    Unit test user interface to SPMClient
    """

    def __init__(self):
        self._status = []
        self._confirm = []
        self._error = []

    def status(self, msg):
        self._status.append(msg)

    def confirm(self, action):
        self._confirm.append(action)

    def error(self, msg):
        self._error.append(msg)


class SPMTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self._tmp_spm = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp_spm, ignore_errors=True)

        minion_config = self.get_temp_config(
            "minion",
            **{
                "spm_logfile": os.path.join(self._tmp_spm, "log"),
                "spm_repos_config": os.path.join(self._tmp_spm, "etc", "spm.repos"),
                "spm_cache_dir": os.path.join(self._tmp_spm, "cache"),
                "spm_build_dir": os.path.join(self._tmp_spm, "build"),
                "spm_build_exclude": [".git"],
                "spm_db_provider": "sqlite3",
                "spm_files_provider": "local",
                "spm_db": os.path.join(self._tmp_spm, "packages.db"),
                "extension_modules": os.path.join(self._tmp_spm, "modules"),
                "file_roots": {"base": [self._tmp_spm]},
                "formula_path": os.path.join(self._tmp_spm, "spm"),
                "pillar_path": os.path.join(self._tmp_spm, "pillar"),
                "reactor_path": os.path.join(self._tmp_spm, "reactor"),
                "assume_yes": True,
                "force": False,
                "verbose": False,
                "cache": "localfs",
                "cachedir": os.path.join(self._tmp_spm, "cache"),
                "spm_repo_dups": "ignore",
                "spm_share_dir": os.path.join(self._tmp_spm, "share"),
            }
        )
        self.ui = SPMTestUserInterface()
        self.client = salt.spm.SPMClient(self.ui, minion_config)
        self.minion_config = minion_config
        for attr in ("client", "ui", "_tmp_spm", "minion_config"):
            self.addCleanup(delattr, self, attr)

    def _create_formula_files(self, formula):
        fdir = os.path.join(self._tmp_spm, formula["definition"]["name"])
        shutil.rmtree(fdir, ignore_errors=True)
        os.mkdir(fdir)
        for path, contents in formula["contents"]:
            path = os.path.join(fdir, path)
            dirname, _ = os.path.split(path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with salt.utils.files.fopen(path, "w") as f:
                f.write(contents)
        return fdir

    def test_build_install(self):
        # Build package
        fdir = self._create_formula_files(_F1)
        with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
            with patch(
                "salt.client.get_local_client",
                MagicMock(return_value=self.minion_opts["conf_file"]),
            ):
                self.client.run(["build", fdir])
        pkgpath = self.ui._status[-1].split()[-1]
        assert os.path.exists(pkgpath)
        # Install package
        with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
            with patch(
                "salt.client.get_local_client",
                MagicMock(return_value=self.minion_opts["conf_file"]),
            ):
                self.client.run(["local", "install", pkgpath])
        # Check filesystem
        for path, contents in _F1["contents"]:
            path = os.path.join(
                self.minion_config["file_roots"]["base"][0],
                _F1["definition"]["name"],
                path,
            )
            assert os.path.exists(path)
            with salt.utils.files.fopen(path, "r") as rfh:
                assert rfh.read() == contents
        # Check database
        with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
            with patch(
                "salt.client.get_local_client",
                MagicMock(return_value=self.minion_opts["conf_file"]),
            ):
                self.client.run(["info", _F1["definition"]["name"]])
        lines = self.ui._status[-1].split("\n")
        for key, line in (
            ("name", "Name: {0}"),
            ("version", "Version: {0}"),
            ("release", "Release: {0}"),
            ("summary", "Summary: {0}"),
        ):
            assert line.format(_F1["definition"][key]) in lines
        # Reinstall with force=False, should fail
        self.ui._error = []
        with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
            with patch(
                "salt.client.get_local_client",
                MagicMock(return_value=self.minion_opts["conf_file"]),
            ):
                self.client.run(["local", "install", pkgpath])
        assert len(self.ui._error) > 0
        # Reinstall with force=True, should succeed
        with patch.dict(self.minion_config, {"force": True}):
            self.ui._error = []
            with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
                with patch(
                    "salt.client.get_local_client",
                    MagicMock(return_value=self.minion_opts["conf_file"]),
                ):
                    self.client.run(["local", "install", pkgpath])
            assert len(self.ui._error) == 0

    def test_failure_paths(self):
        fail_args = (
            ["bogus", "command"],
            ["create_repo"],
            ["build"],
            ["build", "/nonexistent/path"],
            ["info"],
            ["info", "not_installed"],
            ["files"],
            ["files", "not_installed"],
            ["install"],
            ["install", "nonexistent.spm"],
            ["remove"],
            ["remove", "not_installed"],
            ["local", "bogus", "command"],
            ["local", "info"],
            ["local", "info", "/nonexistent/path/junk.spm"],
            ["local", "files"],
            ["local", "files", "/nonexistent/path/junk.spm"],
            ["local", "install"],
            ["local", "install", "/nonexistent/path/junk.spm"],
            ["local", "list"],
            ["local", "list", "/nonexistent/path/junk.spm"],
            # XXX install failure due to missing deps
            # XXX install failure due to missing field
        )

        for args in fail_args:
            self.ui._error = []
            with patch("salt.client.Caller", MagicMock(return_value=self.minion_opts)):
                with patch(
                    "salt.client.get_local_client",
                    MagicMock(return_value=self.minion_opts["conf_file"]),
                ):
                    self.client.run(args)
            assert len(self.ui._error) > 0
