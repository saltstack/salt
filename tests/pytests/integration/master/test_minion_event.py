import logging

import salt.channel.client
import salt.config
import salt.crypt
import salt.utils.args
import salt.utils.jid

log = logging.getLogger(__name__)


def test_minoin_event_blacklist(salt_master, salt_minion, salt_cli, caplog):
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0

    opts = salt.config.minion_config(salt_minion.config_file)
    opts["master_uri"] = "tcp://{}:{}".format(opts["master"], opts["master_port"])

    jid = salt.utils.jid.gen_jid(opts)
    auth = salt.crypt.SAuth(opts)
    tok = auth.gen_token(b"salt")

    load = {
        "cmd": "_minion_event",
        "tok": tok,
        "id": opts["id"],
        "events": [
            {
                "data": {
                    "fun": "test.ping",
                    "arg": [],
                    "jid": jid,
                    "ret": "",
                    "tgt": salt_minion.id,
                    "tgt_type": "glob",
                    "user": "root",
                    "__peer_id": "salt",
                },
                "tag": f"salt/job/{jid}/publish",
            }
        ],
    }
    with caplog.at_level(logging.WARNING):
        with salt.channel.client.ReqChannel.factory(opts) as channel:
            channel.send(load, tries=1, timeout=10000)
            log.info("payload sent, jid was %s", jid)
        assert "Filtering blacklisted" in caplog.text
