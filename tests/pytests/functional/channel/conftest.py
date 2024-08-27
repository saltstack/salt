import ctypes
import multiprocessing

import pytest
from saltfactories.utils import random_string

import salt.crypt
import salt.master
import salt.utils.stringutils
from tests.conftest import FIPS_TESTRUN


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


def transport_ids(value):
    return f"Transport({value})"


@pytest.fixture(params=("zeromq", "tcp"), ids=transport_ids)
def transport(request):
    return request.param


@pytest.fixture
def salt_master(salt_factories, transport):
    config_defaults = {
        "transport": transport,
        "auto_accept": True,
        "sign_pub_messages": False,
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        random_string(f"server-{transport}-master-"),
        defaults=config_defaults,
    )
    return factory


@pytest.fixture
def salt_minion(salt_master, transport):
    config_defaults = {
        "transport": transport,
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": f"tcp://127.0.0.1:{salt_master.config['ret_port']}",
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = salt_master.salt_minion_daemon(
        random_string("server-{transport}-minion-"),
        defaults=config_defaults,
    )
    return factory
