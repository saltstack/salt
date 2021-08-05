"""
tests.pytests.unit.loader.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's loader
"""
import salt.loader
import salt.loader.lazy


def test_raw_mod_functions():
    "Ensure functions loaded by raw_mod are LoaderFunc instances"
    opts = {
        "extension_modules": "",
        "optimization_order": [0],
    }
    ret = salt.loader.raw_mod(opts, "grains", "get")
    for k, v in ret.items():
        assert isinstance(v, salt.loader.lazy.LoadedFunc)
