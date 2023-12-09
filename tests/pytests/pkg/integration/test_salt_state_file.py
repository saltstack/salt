import subprocess

import pytest
from pytestskipmarkers.utils import platform

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def state_name(salt_master):
    name = "some-state"
    if platform.is_windows():
        sls_contents = """
    create_empty_file:
      file.managed:
        - name: C://salt/test/txt
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
    else:
        sls_contents = """
    update:
      pkg.installed:
        - name: bash
    salt_dude:
      user.present:
        - name: dude
        - fullname: Salt Dude
    """
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


def test_salt_state_file(salt_cli, salt_minion, state_name):
    """
    Test state file
    """
    ret = salt_cli.run("state.apply", state_name, minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    if ret.stdout and "Minion did not return" in ret.stdout:
        pytest.skip("Skipping test, state took too long to apply")
    sls_ret = ret.data[next(iter(ret.data))]
    assert "changes" in sls_ret
    assert "name" in sls_ret
