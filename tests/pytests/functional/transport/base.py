import multiprocessing
import stat
import time

import pytest

import salt.transport.base
import salt.transport.tcp
import salt.transport.ws
import salt.transport.zeromq


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


TRANSPORT_MAP = {
    "zeromq": salt.transport.zeromq.PublishServer,
    "tcp": salt.transport.tcp.PublishServer,
    "ws": salt.transport.ws.PublishServer,
}


def test_check_all_transports():
    """
    Ensure we are testing all existing transports. If adding a transport it
    should be tested by 'test_transport_socket_perms_conform'.
    """
    assert sorted(TRANSPORT_MAP.keys()) == sorted(salt.transport.base.TRANSPORTS)


@pytest.mark.parametrize("kind", salt.transport.base.TRANSPORTS)
def test_transport_socket_perms_conform(kind, tmp_path):
    opts = {
        "ipc_mode": "ipc",
        "hash_type": "md5",
        "hash_id": "master",
        "id": "master",
        "ipv6": False,
        "sock_dir": str(tmp_path),
    }
    kwargs = {
        "pub_path": str(tmp_path / "pub.ipc"),
        "pull_path": str(tmp_path / "pull.ipc"),
        "pub_path_perms": 0o660,
    }
    server = TRANSPORT_MAP[kind](opts, **kwargs)

    proc = multiprocessing.Process(target=server.publish_daemon, args=(lambda x: x,))
    proc.start()
    time.sleep(1)
    try:
        pub_path = tmp_path / "pub.ipc"
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

        pull_path = tmp_path / "pull.ipc"
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
