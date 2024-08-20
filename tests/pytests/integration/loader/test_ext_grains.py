import pytest

from tests.conftest import FIPS_TESTRUN


def test_grains_overwrite(salt_cli, salt_master, salt_minion):
    assert not salt_minion.config.get("grains_deep_merge", False)
    # Force a grains sync
    salt_cli.run("saltutil.sync_grains", minion_tgt=salt_minion.id)

    # Check that custom grains are overwritten
    ret = salt_cli.run("grains.items", minion_tgt=salt_minion.id)
    assert ret.data["a_custom"] == {"k2": "v2"}


def test_grains_merge(salt_cli, salt_master):
    minion = salt_master.salt_minion_daemon(
        "test_grains_merge",
        overrides={
            "grains_deep_merge": True,
            # Grains in the minon config won't get merged.
            # "grains": {"a_custom": {"k1": "v1"}},
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    content = """
    def grain():
        return {"a_custom": {"k1": "v1"}}
    """
    with salt_master.state_tree.base.temp_file("_grains/tempcustom.py", content):
        with minion.started():
            salt_cli.run("saltutil.sync_grains", minion_tgt=minion.id)
            ret = salt_cli.run("grains.item", "a_custom", minion_tgt=minion.id)
            assert ret.data["a_custom"] == {"k1": "v1", "k2": "v2"}
