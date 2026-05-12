import getpass
import pathlib

import salt.channel.client


def test_file_recv_path(salt_master, salt_minion):
    config = salt_minion.config.copy()
    config["master_uri"] = f"tcp://127.0.0.1:{salt_master.config['ret_port']}"
    keyfile = f".{getpass.getuser()}_key"
    data = b"asdf"
    load_path_list = ["..", "..", "..", keyfile]
    cachedir = salt_master.config["cachedir"]
    assert (pathlib.Path(cachedir) / keyfile).exists()
    assert (pathlib.Path(cachedir) / keyfile).read_bytes() != data
    with salt.channel.client.ReqChannel.factory(config, crypt="aes") as channel:
        load = {
            "cmd": "_file_recv",
            "id": salt_minion.config["id"],
            "path": load_path_list,
            "size": len(data),
            "tok": channel.auth.gen_token(b"salt"),
            "loc": 0,
            "data": b"asdf",
        }
        ret = channel.send(load)
    assert ret is False
    assert (pathlib.Path(cachedir) / keyfile).exists()
    assert (pathlib.Path(cachedir) / keyfile).read_bytes() != data
