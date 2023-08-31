import pytest

import salt.config
import salt.loader
import salt.roster.sshknownhosts as sshknownhosts
from tests.support.mock import patch


@pytest.fixture
def ALL_DICT():
    yield {
        "server1": {"host": "server1"},
        "server2": {"host": "server2"},
        "server3.local": {"host": "server3.local"},
        "eu-mysql-1.local": {"host": "eu-mysql-1.local"},
        "eu-mysql-2": {"host": "eu-mysql-2"},
        "eu-mysql-2.local": {"host": "eu-mysql-2.local"},
    }


@pytest.fixture
def GLOB_DICT():
    yield {
        "server1": {"host": "server1"},
        "server2": {"host": "server2"},
        "server3.local": {"host": "server3.local"},
    }


@pytest.fixture
def PCRE_DICT():
    yield {"eu-mysql-2": {"host": "eu-mysql-2"}}


@pytest.fixture
def known_hosts():

    yield """
server1 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBD0vTE0R76xiKEXAdebZW0a3xGLeP2Fet/5YHQgprry3wuXzjBJwGcm8PVFNfbK/C7oAgFUg8NVX7xqQnScekJg=
server2 ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAui+dKujjKF92dDdM9hZzCd+BdTDRnvsWqMf88NjushOmFCt/8zXbB1TvYQmdCcy1qXqhmkbgUdtVuLHnhncf/niCtyih3K3ZR7NpecBydcC+0xv0UeXk/xCGcwM2V0BuukrV/5qRqhyG0rK1hd+Iv9fkB0/s8D/HLcEB1/V4g77XxPGnI7lNANFbZpWs1LrnAec7JIkHO9MHEfuhQWZR6+/iIXIwQoc1RCToQbWQFCYFwrnDrAUHC2+izJiP2VDNW6xboVcf6DpwydfYvFdM8Mo97DEcchlwIWhmGl//LpnwafujFZCE5vDveA8X4uKZEXxoCmUPIGfkx6xIzzTkqQ==
server3.local ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBAgKWpCT7JIeK/qzwE5lUQkLRfkRa5WnyyeF+aYCKDUHB4b4Pn+acm8FOca+riulPDY/gJhb0MX3Rf/t6MrEHQA=
eu-mysql-1.local ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEAsuToIp6iqJ3lHPQzCTiNf5F8uf/CjAljuxRjURYCbQydts2lnnqTpjamL1b8/FpvB1dDlA71G79yTftVZ8EqL2VaN0tL242MXaqy2nmeVjy89dtOyk35IHwQe8Bi6mu3vLYCFnysiAvrtLQMFe8jNjndsvf27LNKox8pIAyOyN3hONL+bXEcPB2RjIUL8wS8uTeOueuPbVwc1cHkUuMjlNzsH3l6KMVjJZ8keFdRj8iogV8oZGR3KGoPfX4aZDt9S+L/k97fWkOhSKLWkKbplEcmIjuF5pgZLO3Wf35eLZN12PcHuX7WFWZi+UxjJDW2VLaP867La4YXDEU3LNdPEQ==
eu-mysql-2,eu-mysql-2.local ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBHFnjWT+gnUGRA2zW+LGZdebSkUVKBb6F/XCcDrtBZmaxCNaS/+F6SYzXP4MghCQhXFEPd7MpFnwPV8giU1NUag="""


@pytest.fixture
def configure_loader_modules(salt_master_factory, tmp_path):
    opts = salt_master_factory.config.copy()
    utils = salt.loader.utils(opts)
    runner = salt.loader.runner(opts, utils=utils)

    return {
        sshknownhosts: {
            "__opts__": {},
            "__runner__": runner,
            "__utils__": utils,
        }
    }


def test_all(known_hosts, tmp_path, ALL_DICT):
    with pytest.helpers.temp_file(
        "known_hosts", known_hosts, directory=tmp_path
    ) as known_hosts_file:
        opts = {"ssh_known_hosts_file": str(known_hosts_file)}
        with patch.dict(sshknownhosts.__opts__, opts):
            targets = sshknownhosts.targets(tgt="*")
            assert targets == ALL_DICT


def test_glob(known_hosts, tmp_path, GLOB_DICT):
    with pytest.helpers.temp_file(
        "known_hosts", known_hosts, directory=tmp_path
    ) as known_hosts_file:
        opts = {"ssh_known_hosts_file": str(known_hosts_file)}
        with patch.dict(sshknownhosts.__opts__, opts):
            targets = sshknownhosts.targets(tgt="server*")
            assert targets == GLOB_DICT


def test_pcre(known_hosts, tmp_path, PCRE_DICT):
    with pytest.helpers.temp_file(
        "known_hosts", known_hosts, directory=tmp_path
    ) as known_hosts_file:
        opts = {"ssh_known_hosts_file": str(known_hosts_file)}
        with patch.dict(sshknownhosts.__opts__, opts):
            targets = sshknownhosts.targets(tgt="eu-mysql-2$", tgt_type="pcre")
            assert targets == PCRE_DICT
