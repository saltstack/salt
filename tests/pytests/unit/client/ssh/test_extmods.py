import os
import re
import tarfile

import salt.client.ssh
import salt.fileclient
import salt.loader
from tests.support.mock import MagicMock, patch


def test_internal_modules_are_not_synced_as_extmods(master_opts):
    fsclient = salt.fileclient.FSClient(master_opts)
    tar = MagicMock()
    with patch("tarfile.open", return_value=tar):
        salt.client.ssh.mod_data(fsclient)
    ptrn = re.compile(
        r".*/salt/(modules|states|grains|renderers|returners|utils)/\w+\.py$"
    )
    for call in tar.add.call_args_list:
        assert not ptrn.match(call[0][0])


def test_loader_entry_point_keeps_ssh_extmods_isolated(tmp_path):
    """Each roster target receives only the modules selected for that target."""
    fsclient = MagicMock()
    fsclient.opts = {"cachedir": str(tmp_path), "file_roots": {}}
    paths = {}
    for target in ("web-01", "db-01"):
        directory = tmp_path / target / "_modules"
        directory.mkdir(parents=True)
        (directory / f"{target.replace('-', '_')}.py").write_text(
            f"def ping(): return '{target}'\n", encoding="utf-8"
        )
        paths[target] = str(directory)

    entry_point = MagicMock()
    entry_point.name = "module_dirs"
    entry_point.load.return_value = lambda opts=None: [paths[opts["id"]]]
    with patch(
        "salt.utils.entrypoints.iter_entry_points", return_value=[entry_point]
    ):
        web_mods = salt.client.ssh.mod_data(fsclient, target="web-01")
        db_mods = salt.client.ssh.mod_data(fsclient, target="db-01")

    assert web_mods["version"] != db_mods["version"]
    with tarfile.open(web_mods["file"]) as archive:
        assert "modules/web_01.py" in archive.getnames()
        assert "modules/db_01.py" not in archive.getnames()
        assert archive.extractfile("ext_version").read().decode() == web_mods["version"]
    with tarfile.open(db_mods["file"]) as archive:
        assert "modules/db_01.py" in archive.getnames()
        assert "modules/web_01.py" not in archive.getnames()
        assert archive.extractfile("ext_version").read().decode() == db_mods["version"]


# -- _accepts_loader_opts unit tests ------------------------------------------


def test_accepts_loader_opts_with_positional_arg():
    """Provider with a positional parameter is accepted."""

    def provider(opts):
        return []

    assert salt.loader._accepts_loader_opts(provider) is True


def test_accepts_loader_opts_with_optional_arg():
    """Provider with an optional parameter is accepted."""

    def provider(opts=None):
        return []

    assert salt.loader._accepts_loader_opts(provider) is True


def test_accepts_loader_opts_with_no_args():
    """Provider with no parameters is rejected."""

    def provider():
        return []

    assert salt.loader._accepts_loader_opts(provider) is False


def test_accepts_loader_opts_with_kwargs_only():
    """Provider with only **kwargs is rejected (opts is passed positionally)."""

    def provider(**kwargs):
        return []

    assert salt.loader._accepts_loader_opts(provider) is False


# -- entry-point fallback integration test ------------------------------------


def test_zero_arg_entry_point_called_without_opts(tmp_path):
    """Entry point that takes no args falls back to no-argument call."""
    fsclient = MagicMock()
    fsclient.opts = {"cachedir": str(tmp_path), "file_roots": {}}

    mod_dir = tmp_path / "custom_modules"
    mod_dir.mkdir()
    (mod_dir / "mymod.py").write_text("def run(): pass\n", encoding="utf-8")

    called_with_args = []

    def legacy_provider():
        called_with_args.append("no-args")
        return [str(mod_dir)]

    entry_point = MagicMock()
    entry_point.name = "module_dirs"
    entry_point.load.return_value = legacy_provider
    with patch("salt.utils.entrypoints.iter_entry_points", return_value=[entry_point]):
        mods = salt.client.ssh.mod_data(fsclient, target="host-01")

    # Provider is called once per sync_ref (modules, states, grains, etc.)
    assert len(called_with_args) > 0
    assert all(x == "no-args" for x in called_with_args)
    with tarfile.open(mods["file"]) as archive:
        assert "modules/mymod.py" in archive.getnames()


# -- _key_deploy_run uses per-target mods ------------------------------------


def test_key_deploy_run_uses_per_target_mods():
    """_key_deploy_run must call _target_mod_data with the host, not use a global."""
    mock_mods = {"file": "/tmp/fake.tgz", "version": "abc123"}
    with patch("salt.client.ssh._target_mod_data", return_value=mock_mods) as target_mod:
        with patch("salt.client.ssh.Single") as MockSingle:
            instance = MockSingle.return_value
            instance.shell.copy_id.return_value = ("", "", 0)
            instance.run.return_value = ("", "", 0)

            ssh_obj = MagicMock()
            ssh_obj.opts = {"argv": ["test.ping"]}
            ssh_obj.get_pubkey.return_value = "ssh-rsa AAAA..."
            ssh_obj.fsclient = MagicMock()
            ssh_obj.thin = "/tmp/thin.tgz"

            target = {"user": "root", "passwd": "secret"}
            salt.client.ssh.SSH._key_deploy_run(ssh_obj, "web-01", target, re_run=False)

    target_mod.assert_called_once_with(ssh_obj.fsclient, "web-01")
    # Verify Single received the per-target mods, not a global
    _, kwargs = MockSingle.call_args
    assert kwargs["mods"] is mock_mods


# -- tarball caching ----------------------------------------------------------


def test_mod_data_caches_tarball_on_identical_hash(tmp_path):
    """Second call with identical modules should reuse the cached tarball."""
    fsclient = MagicMock()
    fsclient.opts = {"cachedir": str(tmp_path), "file_roots": {}}

    mod_dir = tmp_path / "shared_modules"
    mod_dir.mkdir()
    (mod_dir / "common.py").write_text("x = 1\n", encoding="utf-8")

    entry_point = MagicMock()
    entry_point.name = "module_dirs"
    entry_point.load.return_value = lambda opts: [str(mod_dir)]

    with patch("salt.utils.entrypoints.iter_entry_points", return_value=[entry_point]):
        first = salt.client.ssh.mod_data(fsclient, target="host-a")
        mtime_after_first = os.path.getmtime(first["file"])

        second = salt.client.ssh.mod_data(fsclient, target="host-b")

    # Same modules → same hash → same file, not recreated
    assert first["file"] == second["file"]
    assert first["version"] == second["version"]
    assert os.path.getmtime(second["file"]) == mtime_after_first
