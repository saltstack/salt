import multiprocessing
import stat
import time

import pytest

import salt.transport.base


@pytest.mark.parametrize("kind", salt.transport.base.TRANSPORTS)
def test_master_ipc_socket_perms(kind, tmp_path):
    opts = {
        "ipc_mode": "ipc",
        "hash_type": "md5",
        "hash_id": "master",
        "id": "master",
        "sock_dir": str(tmp_path),
    }
    server = salt.transport.base.ipc_publish_server("master", opts)

    # IPC Server always uses tcp transport, this could change in the future.
    assert isinstance(server, salt.transport.tcp.PublishServer)

    proc = multiprocessing.Process(target=server.publish_daemon, args=(lambda x: x,))
    proc.start()
    time.sleep(1)
    try:
        pub_path = tmp_path / "master_event_pub.ipc"
        assert pub_path.exists()
        status = pub_path.stat()

        assert status.st_mode & stat.S_IRUSR
        assert status.st_mode & stat.S_IWUSR
        assert not status.st_mode & stat.S_IXUSR

        assert status.st_mode & stat.S_IRGRP
        assert status.st_mode & stat.S_IWGRP
        assert not status.st_mode & stat.S_IXGRP

        assert not status.st_mode & stat.S_IROTH
        assert not status.st_mode & stat.S_IWOTH
        assert not status.st_mode & stat.S_IXOTH

        pull_path = tmp_path / "master_event_pull.ipc"
        status = pull_path.stat()

        assert status.st_mode & stat.S_IRUSR
        assert status.st_mode & stat.S_IWUSR
        assert not status.st_mode & stat.S_IXUSR

        assert not status.st_mode & stat.S_IRGRP
        assert not status.st_mode & stat.S_IWGRP
        assert not status.st_mode & stat.S_IXGRP

        assert not status.st_mode & stat.S_IROTH
        assert not status.st_mode & stat.S_IWOTH
        assert not status.st_mode & stat.S_IXOTH
    finally:
        proc.terminate()
        proc.join()
        proc.close()


@pytest.mark.parametrize("kind", salt.transport.base.TRANSPORTS)
def test_minion_ipc_socket_perms(kind, tmp_path):
    opts = {
        "ipc_mode": "ipc",
        "hash_type": "md5",
        "hash_id": "minion",
        "id": "minion",
        "sock_dir": str(tmp_path),
    }
    server = salt.transport.base.ipc_publish_server("minion", opts)

    # IPC Server always uses tcp transport, this could change in the future.
    assert isinstance(server, salt.transport.tcp.PublishServer)

    proc = multiprocessing.Process(target=server.publish_daemon, args=(lambda x: x,))
    proc.start()
    time.sleep(1)
    try:
        id_hash = salt.transport.base._minion_hash(
            hash_type=opts["hash_type"],
            minion_id=opts.get("hash_id", opts["id"]),
        )
        pub_path = tmp_path / f"minion_event_{id_hash}_pub.ipc"
        assert pub_path.exists()
        status = pub_path.stat()

        assert status.st_mode & stat.S_IRUSR
        assert status.st_mode & stat.S_IWUSR
        assert not status.st_mode & stat.S_IXUSR

        assert not status.st_mode & stat.S_IRGRP
        assert not status.st_mode & stat.S_IWGRP
        assert not status.st_mode & stat.S_IXGRP

        assert not status.st_mode & stat.S_IROTH
        assert not status.st_mode & stat.S_IWOTH
        assert not status.st_mode & stat.S_IXOTH

        pull_path = tmp_path / f"minion_event_{id_hash}_pull.ipc"
        status = pull_path.stat()

        assert status.st_mode & stat.S_IRUSR
        assert status.st_mode & stat.S_IWUSR
        assert not status.st_mode & stat.S_IXUSR

        assert not status.st_mode & stat.S_IRGRP
        assert not status.st_mode & stat.S_IWGRP
        assert not status.st_mode & stat.S_IXGRP

        assert not status.st_mode & stat.S_IROTH
        assert not status.st_mode & stat.S_IWOTH
        assert not status.st_mode & stat.S_IXOTH
    finally:
        proc.terminate()
        proc.join()
        proc.close()
