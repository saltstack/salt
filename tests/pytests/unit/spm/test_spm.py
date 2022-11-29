import os
import shutil

import pytest

import salt.spm
import salt.utils.files
from tests.support.mock import MagicMock, patch


@pytest.fixture()
def f1_content():
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
    return _F1


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


@pytest.fixture()
def setup_spm(tmp_path, minion_opts):
    minion_config = minion_opts.copy()
    minion_config.update(
        {
            "spm_logfile": str(tmp_path / "log"),
            "spm_repos_config": str(tmp_path / "etc" / "spm.repos"),
            "spm_cache_dir": str(tmp_path / "cache"),
            "spm_build_dir": str(tmp_path / "build"),
            "spm_build_exclude": [".git"],
            "spm_db_provider": "sqlite3",
            "spm_files_provider": "local",
            "spm_db": str(tmp_path / "packages.db"),
            "extension_modules": str(tmp_path / "modules"),
            "file_roots": {"base": [str(tmp_path)]},
            "formula_path": str(tmp_path / "spm"),
            "pillar_path": str(tmp_path / "pillar"),
            "reactor_path": str(tmp_path / "reactor"),
            "assume_yes": True,
            "root_dir": str(tmp_path),
            "force": False,
            "verbose": False,
            "cache": "localfs",
            "cachedir": str(tmp_path / "cache"),
            "spm_repo_dups": "ignore",
            "spm_share_dir": str(tmp_path / "share"),
        }
    )
    ui = SPMTestUserInterface()
    client = salt.spm.SPMClient(ui, minion_config)
    return tmp_path, ui, client, minion_config, minion_opts


def _create_formula_files(formula, _tmp_spm):
    fdir = str(_tmp_spm / formula["definition"]["name"])
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


@pytest.fixture()
def patch_local_client(setup_spm):
    _tmp_spm, ui, client, minion_config, minion_opts = setup_spm
    with patch("salt.client.Caller", return_value=minion_opts):
        with patch(
            "salt.client.get_local_client", return_value=minion_opts["conf_file"]
        ):
            yield


def test_build_install(setup_spm, f1_content, patch_local_client):
    # Build package
    _tmp_spm, ui, client, minion_config, minion_opts = setup_spm
    fdir = _create_formula_files(f1_content, _tmp_spm)
    client.run(["build", fdir])
    pkgpath = ui._status[-1].split()[-1]
    assert os.path.exists(pkgpath)
    # Install package
    client.run(["local", "install", pkgpath])
    # Check filesystem
    for path, contents in f1_content["contents"]:
        path = os.path.join(
            minion_config["file_roots"]["base"][0],
            f1_content["definition"]["name"],
            path,
        )
        assert os.path.exists(path)
        with salt.utils.files.fopen(path, "r") as rfh:
            assert rfh.read() == contents
    # Check database
    client.run(["info", f1_content["definition"]["name"]])
    lines = ui._status[-1].split("\n")
    for key, line in (
        ("name", "Name: {0}"),
        ("version", "Version: {0}"),
        ("release", "Release: {0}"),
        ("summary", "Summary: {0}"),
    ):
        assert line.format(f1_content["definition"][key]) in lines
    # Reinstall with force=False, should fail
    ui._error = []
    client.run(["local", "install", pkgpath])
    assert len(ui._error) > 0
    # Reinstall with force=True, should succeed
    with patch.dict(minion_config, {"force": True}):
        ui._error = []
        with patch("salt.client.Caller", MagicMock(return_value=minion_opts)):
            with patch(
                "salt.client.get_local_client",
                MagicMock(return_value=minion_opts["conf_file"]),
            ):
                client.run(["local", "install", pkgpath])
        assert len(ui._error) == 0


def test_repo_paths(setup_spm):
    _tmp_spm, ui, client, minion_config, minion_opts = setup_spm
    ui._error = []
    with patch("salt.client.Caller", MagicMock(return_value=minion_opts)):
        with patch(
            "salt.client.get_local_client",
            MagicMock(return_value=minion_opts["conf_file"]),
        ):
            client.run(["create_repo", "."])
    assert len(ui._error) == 0


def test_failure_paths(setup_spm, patch_local_client):
    _tmp_spm, ui, client, minion_config, minion_opts = setup_spm
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
        ui._error = []
        client.run(args)
        assert len(ui._error) > 0
