import salt.minion
from tests.support.mock import patch


def test_minion_grains_in_opts():
    """
    Minion does not generate grains when they are already in opts
    """
    opts = {"random_startup_delay": 0, "grains": {"foo": "bar"}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts)
        assert minion.opts["grains"] == opts["grains"]
        grainsfunc.assert_not_called()


def test_minion_grains_not_in_opts():
    """
    Minion generates grains when they are not already in opts
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()
