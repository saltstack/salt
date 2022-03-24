"""
tests.pytests.unit.test_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's config modulet
"""
import salt.config


def test_call_id_function(tmp_path):
    "Defining id_function works as expected"
    cache_dir = tmp_path / "cache"
    extmods = tmp_path / "extmods"
    opts = {
        "id_function": {"grains.get": {"key": "osfinger"}},
        "cachedir": str(cache_dir),
        "extension_modules": str(extmods),
        "grains": {"osfinger": "meh"},
        "optimization_order": [0],
    }
    ret = salt.config.call_id_function(opts)
    assert ret == "meh"
