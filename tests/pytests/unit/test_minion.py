import salt.minion
from tests.support.mock import patch


def test_minion_load_grains_false():
    """
    Minion does not generate grains when load_grains is False
    """
    opts = {"random_startup_delay": 0, "grains": {"foo": "bar"}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=False)
        assert minion.opts["grains"] == opts["grains"]
        grainsfunc.assert_not_called()


def test_minion_load_grains_true():
    """
    Minion generates grains when load_grains is True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=True)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()


def test_minion_load_grains_default():
    """
    Minion load_grains defaults to True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()
