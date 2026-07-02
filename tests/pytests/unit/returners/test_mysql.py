import pytest

from salt.returners import mysql
from tests.support.mock import patch


def test_get_options_does_not_leak_top_level_user_opt():
    """
    Regression test for #32567.

    salt-ssh constructs the returner loader with an empty ``__salt__``, so
    ``get_returner_options`` falls back to ``__opts__`` for config lookups.
    The master's top-level ``user`` opt (the system user salt runs as)
    must not mask the configured ``mysql.user`` when the master config
    writes the mysql section as a nested mapping.
    """
    opts = {
        # the master's top-level system user -- previously leaked through
        # as the mysql user.
        "user": "root",
        # mysql credentials written as a nested mapping (the common form
        # in ``/etc/salt/master.d/mysql.conf``).
        "mysql": {
            "host": "db.example.com",
            "user": "salt-db-user",
            "pass": "secret",
            "db": "salt",
            "port": 3306,
        },
    }
    with patch.object(mysql, "__opts__", opts, create=True), patch.object(
        mysql, "__salt__", {}, create=True
    ):
        options = mysql._get_options()
    assert options["user"] == "salt-db-user"
    assert options["host"] == "db.example.com"
    assert options["pass"] == "secret"
    assert options["db"] == "salt"
    assert options["port"] == 3306


def test_get_options_honors_flat_dotted_keys():
    """
    Companion to the regression test above: the historical
    ``mysql.user: foo`` flat-key form must keep working.
    """
    opts = {
        "user": "root",
        "mysql.host": "db.example.com",
        "mysql.user": "salt-db-user",
        "mysql.pass": "secret",
        "mysql.db": "salt",
        "mysql.port": 3306,
    }
    with patch.object(mysql, "__opts__", opts, create=True), patch.object(
        mysql, "__salt__", {}, create=True
    ):
        options = mysql._get_options()
    assert options["user"] == "salt-db-user"
    assert options["host"] == "db.example.com"
    assert options["pass"] == "secret"
    assert options["db"] == "salt"
    assert options["port"] == 3306


def test_returner_with_bytes():
    ret = {
        "success": True,
        "return": b"bytes",
        "retcode": 0,
        "jid": "20221101172203459989",
        "fun": "file.read",
        "fun_args": ["/fake/path", {"binary": True}],
        "id": "minion-1",
    }
    with patch.object(mysql, "_get_serv"):
        try:
            mysql.returner(ret)
        except TypeError:
            pytest.fail("Data not decoded properly")


def test_save_load_with_bytes():
    load = {
        "return": b"bytes",
        "jid": "20221101172203459989",
    }
    decoded_load = {
        "return": "bytes",
        "jid": "20221101172203459989",
    }
    with patch.object(mysql, "_get_serv"):
        try:
            mysql.save_load(load["jid"], load)
        except TypeError:
            pytest.fail("Data not decoded properly")
