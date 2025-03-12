import pathlib
import stat


def test_master_event_pub_ipc_perms(salt_master):
    pub_path = pathlib.Path(salt_master.config["sock_dir"]) / "master_event_pub.ipc"
    assert pub_path.exists()
    status = pub_path.stat()
    assert status.st_mode & stat.S_IRUSR
    assert status.st_mode & stat.S_IWUSR
    assert status.st_mode & stat.S_IRGRP
    assert status.st_mode & stat.S_IWGRP
