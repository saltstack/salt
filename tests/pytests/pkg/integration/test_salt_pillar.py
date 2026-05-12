import subprocess

import pytest
from pytestskipmarkers.utils import platform

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def pillar_name(salt_master):
    name = "info"
    top_file_contents = """
    base:
      '*':
        - test
    """
    test_file_contents = f"""
    {name}: test
    """
    with salt_master.pillar_tree.base.temp_file(
        "top.sls", top_file_contents
    ), salt_master.pillar_tree.base.temp_file("test.sls", test_file_contents):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.pillar_tree.base.write_path),
                ],
                check=False,
            )
        yield name


def test_salt_pillar(salt_cli, salt_minion, salt_master, pillar_name):
    """
    Test pillar.items
    """
    assert salt_master.is_running()

    ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert pillar_name in ret.data
