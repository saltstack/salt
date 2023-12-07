import pytest

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
        yield name


def test_salt_pillar(salt_cli, salt_minion, pillar_name):
    """
    Test pillar.items
    """
    ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert pillar_name in ret.data
