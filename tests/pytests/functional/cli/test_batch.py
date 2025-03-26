"""
tests.pytests.functional.cli.test_batch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import salt.cli.batch
import salt.config
import salt.utils.jid
from tests.support.mock import Mock, patch


class MockPub:
    """
    Mock salt.client.LocalClient.pub method
    """

    calls = 0
    initial_ping = False
    batch1_jid = None
    batch1_tgt = None
    batch2_jid = None
    batch2_tgt = None
    batch3_jid = None
    batch3_tgt = None

    def __call__(self, tgt, fun, *args, **kwargs):
        if tgt == "minion*" and fun == "test.ping":
            MockPub.calls += 1
            MockPub.initial_ping = salt.utils.jid.gen_jid({})
            pub_ret = {
                "jid": MockPub.initial_ping,
                "minions": ["minion0", "minion1", "minion2", "minion3"],
            }
        elif fun == "state.sls":
            if MockPub.calls == 1:
                MockPub.calls += 1
                MockPub.batch1_tgt = list(tgt)
                MockPub.batch1_jid = jid = salt.utils.jid.gen_jid({})
                pub_ret = {"jid": jid, "minions": tgt}
            elif MockPub.calls == 2:
                MockPub.calls += 1
                MockPub.batch2_tgt = tgt
                MockPub.batch2_jid = jid = salt.utils.jid.gen_jid({})
                pub_ret = {"jid": jid, "minions": tgt}
            elif MockPub.calls == 3:
                MockPub.calls += 1
                MockPub.batch3_tgt = tgt
                MockPub.batch3_jid = jid = salt.utils.jid.gen_jid({})
                pub_ret = {"jid": jid, "minions": tgt}
        elif fun == "saltutil.find_job":
            jid = salt.utils.jid.gen_jid({})
            pub_ret = {"jid": jid, "minions": tgt}
        return pub_ret


class MockSubscriber:
    """
    Mock salt.transport.ipc IPCMessageSubscriber in order to inject events into
    salt.utils.Event
    """

    calls = 0
    pubret = None

    def __init__(self, *args, **kwargs):
        return

    def recv(self, timeout=None):
        """
        Mock IPCMessageSubcriber read method.

        - Return events for initial ping
        - Returns event for a minion in first batch to cause second batch to get sent.
        - Returns 5 null events on first iteration of second batch to go back to first batch.
        - On second iteration of first batch, send an event from second batch which will get cached.
        - Return events for the rest of the batches.
        """
        if MockSubscriber.pubret.initial_ping:
            # Send ping responses for 4 minions
            jid = MockSubscriber.pubret.initial_ping
            if MockSubscriber.calls == 0:
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id="minion0", fun="test.ping")
            elif MockSubscriber.calls == 1:
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id="minion1", fun="test.ping")
            elif MockSubscriber.calls == 2:
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id="minion2", fun="test.ping")
            elif MockSubscriber.calls == 3:
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id="minion3", fun="test.ping")
        if MockSubscriber.pubret.batch1_jid:
            jid = MockSubscriber.pubret.batch1_jid
            tgt = MockSubscriber.pubret.batch1_tgt
            if MockSubscriber.calls == 4:
                # Send a return for first minion in first batch. This causes the
                # second batch to get sent.
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id=tgt[0], fun="state.sls")
        if MockSubscriber.pubret.batch2_jid:
            if MockSubscriber.calls <= 10:
                # Skip the first iteration of the second batch; this will cause
                # batch logic to go back to iterating over the first batch.
                MockSubscriber.calls += 1
                return
            elif MockSubscriber.calls == 11:
                # Send the minion from the second batch, This event will get cached.
                jid = MockSubscriber.pubret.batch2_jid
                tgt = MockSubscriber.pubret.batch2_tgt
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id=tgt[0], fun="state.sls")
        if MockSubscriber.calls == 12:
            jid = MockSubscriber.pubret.batch1_jid
            tgt = MockSubscriber.pubret.batch1_tgt
            MockSubscriber.calls += 1
            return self._ret(jid, minion_id=tgt[1], fun="state.sls")
        if MockSubscriber.pubret.batch3_jid:
            jid = MockSubscriber.pubret.batch3_jid
            tgt = MockSubscriber.pubret.batch3_tgt
            if MockSubscriber.calls == 13:
                MockSubscriber.calls += 1
                return self._ret(jid, minion_id=tgt[0], fun="state.sls")
        return

    def _ret(self, jid, minion_id, fun, _return=True, _retcode=0):
        """
        Create a mock return from a jid, minion, and fun
        """
        dumped = salt.payload.dumps(
            {
                "fun_args": [],
                "jid": jid,
                "return": _return,
                "retcode": 0,
                "success": True,
                "cmd": "_return",
                "fun": fun,
                "id": minion_id,
                "_stamp": "2021-05-24T01:23:25.373194",
            },
            use_bin_type=True,
        )
        tag = f"salt/job/{jid}/ret/{minion_id}".encode()
        return b"".join([tag, b"\n\n", dumped])

    def connect(self, timeout=None):
        pass


def test_batch_issue_56273():
    """
    Regression test for race condition in batch logic.
    https://github.com/saltstack/salt/issues/56273
    """

    mock_pub = MockPub()
    MockSubscriber.pubret = mock_pub

    def returns_for_job(jid):
        return True

    opts = {
        "conf_file": "",
        "tgt": "minion*",
        "fun": "state.sls",
        "arg": ["foo"],
        "timeout": 1,
        "gather_job_timeout": 1,
        "batch": 2,
        "extension_modules": "",
        "failhard": True,
    }
    with patch("salt.transport.tcp.PublishClient", MockSubscriber):
        batch = salt.cli.batch.Batch(opts, quiet=True)
        with patch.object(batch.local, "pub", Mock(side_effect=mock_pub)):
            with patch.object(
                batch.local, "returns_for_job", Mock(side_effect=returns_for_job)
            ):
                ret = list(batch.run())
    assert len(ret) == 4
    for val, _ in ret:
        values = list(val.values())
        assert len(values) == 1
        assert values[0] is True
