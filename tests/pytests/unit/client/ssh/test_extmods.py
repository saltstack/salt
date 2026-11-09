import re
import tarfile

import salt.client.ssh
import salt.fileclient
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
            "def ping(): return True\n", encoding="utf-8"
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
