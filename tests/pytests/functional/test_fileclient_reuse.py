import pytest

import salt.loader
import salt.pillar
import salt.state
import salt.utils.cache
import salt.utils.jinja
from tests.support.mock import patch


@pytest.fixture
def mock_cached_loader():
    """
    Mock the SaltCacheLoader

    The mock keeps track of the number of
    instantiations and the most recent args and kwargs.
    """

    class CacheLoader(salt.utils.jinja.SaltCacheLoader):
        args = []
        kwargs = {}
        calls = 0

        def __init__(self, *args, **kwargs):
            self.__class__.calls += 1
            self.__class__.args = args
            self.__class__.kwargs = kwargs
            super().__init__(*args, **kwargs)

    with patch("salt.utils.jinja.SaltCacheLoader", CacheLoader):
        yield CacheLoader


def test_pillar_tops(temp_salt_master, temp_salt_minion, tmp_path, mock_cached_loader):
    """
    pillar fileclient is used while rendering pillar tops
    """
    tops = """
    base:
      "*":
        - test_pillar
    """
    pillarsls = """
    foo: bar
    """
    opts = temp_salt_master.config.copy()

    with temp_salt_master.pillar_tree.base.temp_file("top.sls", tops):
        with temp_salt_master.pillar_tree.base.temp_file("test_pillar.sls", pillarsls):
            grains = salt.loader.grains(opts)
            pillar = salt.pillar.Pillar(
                opts,
                grains,
                temp_salt_minion.id,
                "base",
            )
            pillar.get_tops()
            assert mock_cached_loader.calls == 1
            assert "_file_client" in mock_cached_loader.kwargs
            assert mock_cached_loader.kwargs["_file_client"] == pillar.client


def test_pillar_render(
    temp_salt_master, temp_salt_minion, tmp_path, mock_cached_loader
):
    """
    pillar fileclient is used while rendering jinja pillar
    """
    tops = """
    base:
      "*":
        - test_pillar
    """
    pillarsls = """
    foo: bar
    """
    opts = temp_salt_master.config.copy()

    with temp_salt_master.pillar_tree.base.temp_file("top.sls", tops):
        with temp_salt_master.pillar_tree.base.temp_file("test_pillar.sls", pillarsls):
            grains = salt.loader.grains(opts)
            pillar = salt.pillar.Pillar(
                opts,
                grains,
                temp_salt_minion.id,
                "base",
            )
            pdata = pillar.render_pillar({"base": ["test_pillar"]})
            assert pdata == ({"foo": "bar"}, [])
            assert mock_cached_loader.calls == 1
            assert "_file_client" in mock_cached_loader.kwargs
            assert mock_cached_loader.kwargs["_file_client"] == pillar.client


def test_highstate(temp_salt_master, temp_salt_minion, tmp_path, mock_cached_loader):
    """
    pillar fileclient is used while rendering pillar tops
    """
    statesls = """
    test_state:
      cmd.run:
        - name: echos foo
    """
    opts = temp_salt_master.config.copy()

    with temp_salt_master.state_tree.base.temp_file("test_state.sls", statesls):
        highstate = salt.state.HighState(
            opts,
        )
        a = highstate.render_highstate({"base": ["test_state"]})
        assert mock_cached_loader.calls == 1
        assert "_file_client" in mock_cached_loader.kwargs
        assert mock_cached_loader.kwargs["_file_client"] == highstate.client
