"""
Pillar cache tests
"""
import pytest


@pytest.fixture()
def pillar_cache_tree(pillar_state_tree, pillar_salt_minion, pillar_salt_call_cli):
    top_file = """
    base:
      '{}':
        - test
    """.format(
        pillar_salt_minion.id
    )
    test_pillar = """
    test: one
    test2: two
    """
    top_tempfile = pytest.helpers.temp_file("top.sls", top_file, pillar_state_tree)
    pillar_tempfile = pytest.helpers.temp_file(
        "test.sls", test_pillar, pillar_state_tree
    )
    try:
        with top_tempfile, pillar_tempfile:
            ret = pillar_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.returncode == 0
            assert ret.data is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = pillar_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


@pytest.fixture()
def pillar_cache_tree_no_refresh(
    pillar_state_tree, pillar_salt_minion, pillar_salt_call_cli
):
    """
    setup the pillar tree but do not run saltutil.refresh_pillar
    after setting up pillar
    """
    ret = pillar_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
    top_file = """
    base:
      '{}':
        - test
    """.format(
        pillar_salt_minion.id
    )
    test_pillar = """
    test: one
    test2: two
    test3: three
    """
    top_tempfile = pytest.helpers.temp_file("top.sls", top_file, pillar_state_tree)
    pillar_tempfile = pytest.helpers.temp_file(
        "test.sls", test_pillar, pillar_state_tree
    )
    try:
        with top_tempfile, pillar_tempfile:
            ret = pillar_salt_call_cli.run(
                "saltutil.refresh_pillar", wait=True, clean_cache=False
            )
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = pillar_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.returncode == 0
        assert ret.data is True


def test_pillar_cache_refresh(pillar_cache_tree, pillar_salt_call_cli):
    """
    Test pillar cache updates after a refresh_pillar
    """
    ret = pillar_salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "test" in ret.data
    assert "test2" in ret.data


def test_pillar_cache_items(pillar_cache_tree_no_refresh, pillar_salt_call_cli):
    """
    Test pillar cache does not refresh pillar when using pillar.items
    """
    # pillar.items should be empty
    pillar_before = pillar_salt_call_cli.run("pillar.items").data
    pillar_salt_call_cli.run("saltutil.refresh_pillar", wait=True)
    # pillar.items should contain the new pillar data
    ret = pillar_salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "test" in ret.data
    assert "test2" in ret.data
    assert ret.data != pillar_before


def test_pillar_cache_passes_extra_minion_data(pillar_salt_call_cli):
    """
    Test that pillar cache does not disable passing of
    extra_minion_data to external pillars
    """
    ret = pillar_salt_call_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    assert "hi" in ret.data
    assert ret.data["hi"] == "there"
