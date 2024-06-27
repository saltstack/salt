import subprocess
import types

import pytest
from pytestskipmarkers.utils import platform
from saltfactories.utils.functional import MultiStateResult

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def files(tmp_path):
    return types.SimpleNamespace(
        fpath_1=tmp_path / "fpath_1.txt",
        fpath_2=tmp_path / "fpath_2.txt",
        fpath_3=tmp_path / "fpath_3.txt",
    )


@pytest.fixture
def state_name(files, salt_master):
    name = "some-state"
    sls_contents = f"""
    create-fpath-1-file:
      file.managed:
        - name: {files.fpath_1}

    create-fpath-2-file:
      file.managed:
        - name: {files.fpath_2}

    create-fpath-3-file:
      file.managed:
        - name: {files.fpath_3}
    """
    assert files.fpath_1.exists() is False
    assert files.fpath_2.exists() is False
    assert files.fpath_3.exists() is False
    with salt_master.state_tree.base.temp_file(f"{name}.sls", sls_contents):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.state_tree.base.write_path),
                ],
                check=False,
            )
        yield name


def test_salt_state_file(salt_cli, salt_minion, salt_master, state_name, files):
    """
    Test state file
    """
    assert files.fpath_1.exists() is False
    assert files.fpath_2.exists() is False
    assert files.fpath_3.exists() is False
    assert salt_master.is_running()

    ret = salt_cli.run("state.apply", state_name, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    if ret.stdout and "Minion did not return" in ret.stdout:
        pytest.skip("Skipping test, state took too long to apply")

    for state_return in MultiStateResult(ret.data):
        assert state_return.result is True

    assert files.fpath_1.exists() is True
    assert files.fpath_2.exists() is True
    assert files.fpath_3.exists() is True
