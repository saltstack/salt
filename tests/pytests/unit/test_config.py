"""
tests.pytests.unit.test_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's config modulet
"""

import pathlib

import pytest

import salt.config
import salt.syspaths
import salt.utils.files


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


def test_prepend_root_dir(tmp_path):
    root = tmp_path / "root"
    opts = {
        "root_dir": root,
        "foo": str(pathlib.Path(salt.syspaths.ROOT_DIR) / "var" / "foo"),
    }
    salt.config.prepend_root_dir(opts, ["foo"])
    assert opts["foo"] == str(root / "var" / "foo")


@pytest.mark.parametrize("grains_value", ["", '""', "[]", "foo", "42", "[1, 2]"])
def test_minion_config_non_dict_grains_reverts_to_default(grains_value, tmp_path):
    """
    The 'grains' minion config option must be a mapping. Any non-dict
    value (an empty scalar, a string, a number, a list, ...) should be
    silently defaulted to an empty dict instead of being left as-is,
    which previously caused a crash in the loader when it tried to
    build the NamespacedDictWrapper for __grains__. See issue #61321.
    """
    conf_file = str(tmp_path / "minion")
    with salt.utils.files.fopen(conf_file, "w") as wfh:
        wfh.write(f"root_dir: /\nkey_logfile: key\ngrains: {grains_value}\n")
    config = salt.config.minion_config(conf_file)
    assert config["grains"] == {}
