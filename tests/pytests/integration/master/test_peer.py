import shutil

import pytest
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN


@pytest.fixture(scope="module")
def pillar_state_tree(tmp_path_factory):
    _pillar_state_tree = tmp_path_factory.mktemp("pillar")
    try:
        yield _pillar_state_tree
    finally:
        shutil.rmtree(str(_pillar_state_tree), ignore_errors=True)


@pytest.fixture(scope="module")
def peer_salt_master_config(pillar_state_tree):
    return {
        "pillar_roots": {"base": [str(pillar_state_tree)]},
        "open_mode": True,
        "peer": {
            ".*": ["test.ping"],
            "peer-comm-minion.*": [
                {
                    "G@hello_peer:beer": ["grains.get"],
                }
            ],
        },
    }


@pytest.fixture(scope="module")
def peer_salt_master(
    salt_factories, pillar_state_tree, vault_port, peer_salt_master_config
):
    factory = salt_factories.salt_master_daemon(
        random_string("peer-comm-master", uppercase=False),
        defaults=peer_salt_master_config,
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "publish_signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def peer_salt_minion_1(peer_salt_master):
    assert peer_salt_master.is_running()
    factory = peer_salt_master.salt_minion_daemon(
        random_string("peer-comm-minion-1", uppercase=False),
        defaults={"open_mode": True, "grains": {"hello_peer": "beer"}},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="module")
def peer_salt_minion_2(peer_salt_master):
    assert peer_salt_master.is_running()
    factory = peer_salt_master.salt_minion_daemon(
        random_string("peer-comm-minion-2", uppercase=False),
        defaults={"open_mode": True},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="module")
def peer_salt_minion_3(peer_salt_master):
    assert peer_salt_master.is_running()
    factory = peer_salt_master.salt_minion_daemon(
        random_string("peer-comm-minion-3", uppercase=False),
        defaults={"open_mode": True},
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.mark.parametrize(
    "source,target", ((x, y) for x in range(1, 4) for y in range(1, 4) if x != y)
)
def test_peer_communication(source, target, request, grains):
    if grains["os"] == "Fedora" and grains["osmajorrelease"] >= 40:
        pytest.skip(f"Temporary skip on {grains['osfinger']}")
    cli = request.getfixturevalue(f"peer_salt_minion_{source}").salt_call_cli()
    tgt = request.getfixturevalue(f"peer_salt_minion_{target}").id
    ret = cli.run("publish.publish", tgt, "test.ping")
    assert ret.returncode == 0
    assert ret.data
    assert tgt in ret.data
    assert ret.data[tgt] is True


def test_peer_communication_denied(peer_salt_minion_1, peer_salt_minion_2):
    tgt = peer_salt_minion_2.id
    ret = peer_salt_minion_1.salt_call_cli().run(
        "publish.publish", tgt, "cmd.run", "echo pwned"
    )
    assert ret.returncode == 0
    assert ret.data == {}


@pytest.mark.parametrize("source", [2, 3])
def test_peer_communication_limited_target_allowed(source, peer_salt_minion_1, request):
    cli = request.getfixturevalue(f"peer_salt_minion_{source}").salt_call_cli()
    tgt = peer_salt_minion_1.id
    ret = cli.run("publish.publish", tgt, "grains.get", "hello_peer")
    assert ret.returncode == 0
    assert ret.data
    assert tgt in ret.data
    assert ret.data[tgt] == "beer"


@pytest.mark.parametrize(
    "source,target", ((x, y) for x in range(1, 4) for y in range(2, 4) if x != y)
)
def test_peer_communication_limited_target_denied(source, target, request):
    cli = request.getfixturevalue(f"peer_salt_minion_{source}").salt_call_cli()
    tgt = request.getfixturevalue(f"peer_salt_minion_{target}").id
    ret = cli.run("publish.publish", tgt, "grains.get", "hello_peer")
    assert ret.returncode == 0
    assert ret.data == {}
