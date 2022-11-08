import pytest

from salt.returners import mysql
from tests.support.mock import patch


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
