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


# ---------------------------------------------------------------------------
# client_config: master_port -> ret_port translation
#
# ``/etc/salt/client`` is a dedicated client config file, so operators
# reach for ``master_port`` (the minion-side spelling for "the port to
# reach the master on") rather than ``ret_port`` (the master-side
# spelling for "the port we listen on").  When only ``master_port`` is
# set, ``client_config`` promotes it into ``ret_port`` so the sign-in
# handshake does not silently fall back to 4506.  When ``ret_port`` is
# set explicitly the operator's value wins -- the translation is
# strictly additive.
# ---------------------------------------------------------------------------


def _write_client_config(tmp_path, body):
    """
    Lay out a config dir with a ``client`` file alongside a ``master``
    stub.  ``client_config`` keys off the sibling of the path argument
    (``<config_dir>/client``), so a path pointing at the master file in
    the same directory is enough to activate the dedicated-client path.
    """
    conf_dir = tmp_path / "etc_salt"
    conf_dir.mkdir()
    master_path = conf_dir / "master"
    master_path.write_text("")
    client_path = conf_dir / "client"
    client_path.write_text(body)
    return master_path


def test_client_config_master_port_promoted_to_ret_port(tmp_path):
    """Only ``master_port`` set in the client config -> ret_port follows."""
    master_path = _write_client_config(
        tmp_path, "master: salt.example.com\nmaster_port: 9999\n"
    )
    opts = salt.config.client_config(str(master_path))
    assert opts["ret_port"] == 9999
    assert opts["master_port"] == 9999
    # Sanity: this was flagged as a remote-client config.
    assert opts["__role"] == "client"


def test_client_config_explicit_ret_port_wins_over_master_port(tmp_path):
    """
    Both ``master_port`` and ``ret_port`` set -> the explicit ``ret_port``
    wins.  The master_port -> ret_port translation only kicks in when
    ret_port is absent from the raw file.
    """
    master_path = _write_client_config(
        tmp_path, "master: salt.example.com\nmaster_port: 9999\nret_port: 7777\n"
    )
    opts = salt.config.client_config(str(master_path))
    assert opts["ret_port"] == 7777
    assert opts["master_port"] == 9999


def test_client_config_only_ret_port_set(tmp_path):
    """
    Only ``ret_port`` set -> stays as-is.  The master defaults don't
    carry ``master_port`` (that's a minion-flavoured key), so if the
    operator didn't put it in the client file we shouldn't invent one.
    """
    master_path = _write_client_config(
        tmp_path, "master: salt.example.com\nret_port: 7777\n"
    )
    opts = salt.config.client_config(str(master_path))
    assert opts["ret_port"] == 7777
    assert "master_port" not in opts


def test_client_config_neither_port_set_uses_defaults(tmp_path):
    """
    Neither port set -> ``ret_port`` stays at its baked-in default
    (4506) and ``master_port`` is NOT invented (same reasoning as the
    only-ret_port case).
    """
    master_path = _write_client_config(tmp_path, "master: salt.example.com\n")
    opts = salt.config.client_config(str(master_path))
    assert opts["ret_port"] == 4506
    assert "master_port" not in opts
