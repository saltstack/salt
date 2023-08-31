import ctypes
import multiprocessing

import pytest

import salt.crypt
import salt.master
import salt.utils.stringutils


@pytest.fixture(autouse=True)
def _prepare_aes():
    old_aes = salt.master.SMaster.secrets.get("aes")
    try:
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "reload": salt.crypt.Crypticle.generate_key_string,
        }
    finally:
        if old_aes:
            salt.master.SMaster.secrets["aes"] = old_aes
