import salt.loader
import salt.loader.lazy


def test_raw_mod():
    opts = {
        "extension_modules": "",
        "optimization_order": [0],
    }
    ret = salt.loader.raw_mod(opts, "grains", "get")
    for k, v in ret.items():
        assert isinstance(v, salt.loader.lazy.LoadedFunc)
