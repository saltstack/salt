import pathlib
import stat


def test_master_event_pub_ipc_perms(salt_master):
    pub_path = pathlib.Path(salt_master.config["sock_dir"]) / "master_event_pub.ipc"
    assert pub_path.exists()
    assert pub_path.stat().st_mode & stat.S_IRUSR
    assert pub_path.stat().st_mode & stat.S_IRGRP
