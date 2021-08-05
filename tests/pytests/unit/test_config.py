import salt.config


def test_call_id_function(tmp_path):
    cache_dir = tmp_path / "cache"
    extmods = tmp_path / "extmods"
    opts = {
        "id_function": {"grains.get": {"key": "osfinger"}},
        "cachedir": cache_dir,
        "extension_modules": extmods,
        "grains": {"osfinger": "meh"},
        "optimization_order": [0],
    }
    ret = salt.config.call_id_function(opts)
    assert ret == "meh"
