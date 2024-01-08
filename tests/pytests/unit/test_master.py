import pathlib
import time

import salt.master
from tests.support.mock import patch


def test_fileserver_duration():
    with patch("salt.master.FileserverUpdate._do_update") as update:
        start = time.time()
        salt.master.FileserverUpdate.update(1, {}, 1)
        end = time.time()
        # Interval is equal to timeout so the _do_update method will be called
        # one time.
        update.called_once()
        # Timeout is 1 second
        assert 2 > end - start > 1


def test_syndic_return_cache_dir_creation(encrypted_requests):
    """master's cachedir for a syndic will be created by AESFuncs._syndic_return method"""
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert (cachedir / "syndics").exists()
    assert (cachedir / "syndics" / "mamajama").exists()


def test_syndic_return_cache_dir_creation_traversal(encrypted_requests):
    """
    master's  AESFuncs._syndic_return method cachdir creation is not vulnerable to a directory traversal
    """
    cachedir = pathlib.Path(encrypted_requests.opts["cachedir"])
    assert not (cachedir / "syndics").exists()
    encrypted_requests._syndic_return(
        {
            "id": "../mamajama",
            "jid": "",
            "return": {},
        }
    )
    assert not (cachedir / "syndics").exists()
    assert not (cachedir / "mamajama").exists()
