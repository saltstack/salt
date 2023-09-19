import pathlib
import time
import os

import salt.crypt

def test_cluster_key_rotation(
    cluster_master_1, cluster_master_2, cluster_master_3, cluster_minion_1,
    cluster_cache_path,
):
    cli = cluster_master_2.salt_cli(timeout=120)
    ret = cli.run("test.ping", minion_tgt="cluster-minion-1")
    assert ret.data is True

    # Validate the aes session key for all masters match
    keys = set()
    for master in (cluster_master_1, cluster_master_2, cluster_master_3,):
        config = cluster_minion_1.config.copy()
        config["master_uri"] = f"tcp://{master.config['interface']}:{master.config['ret_port']}"
        auth = salt.crypt.SAuth(config)
        auth.authenticate()
        assert "aes" in auth._creds
        keys.add(auth._creds["aes"])

    assert len(keys) == 1
    orig_aes = keys.pop()

    # Create a drop file and wait for the master to do a key rotation.
    dfpath = pathlib.Path(cluster_master_1.config["cachedir"]) / ".dfn"
    assert not dfpath.exists()
    salt.crypt.dropfile(
        cluster_master_1.config["cachedir"],
        user=os.getlogin(),
        master_id=cluster_master_1.config["id"],
    )
    assert dfpath.exists()
    timeout = 2 * cluster_master_1.config["loop_interval"]
    start = time.monotonic()
    while True:
        if not dfpath.exists():
            break
        if time.monotonic() - start > timeout:
            assert False, f"Drop file never removed {dfpath}"

    keys = set()

    # Validate the aes session key for all masters match
    for master in (cluster_master_1, cluster_master_2, cluster_master_3,):
        config = cluster_minion_1.config.copy()
        config["master_uri"] = f"tcp://{master.config['interface']}:{master.config['ret_port']}"
        auth = salt.crypt.SAuth(config)
        auth.authenticate()
        assert "aes" in auth._creds
        keys.add(auth._creds["aes"])

    assert len(keys) == 1
    # Validate the aes session key actually changed
    assert orig_aes != keys.pop()
