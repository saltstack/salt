"""
tests.pytests.functional.cli.test_batch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import salt.cli.batch
import salt.config
import salt.returners.local_cache as local_cache
import salt.utils.files
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
    Mock the event bus publish client subscriber in order to inject events into
    salt.utils.event.Event
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


class MockPubSingleJid:
    """
    Mock salt.client.LocalClient.pub that captures passed JIDs.
    """

    calls = 0
    initial_ping = False
    captured_jids = []
    batch_tgts = []

    def __call__(self, tgt, fun, *args, **kwargs):
        passed_jid = kwargs.get("jid", "")
        if tgt == "minion*" and fun == "test.ping":
            MockPubSingleJid.calls += 1
            MockPubSingleJid.initial_ping = salt.utils.jid.gen_jid({})
            pub_ret = {
                "jid": MockPubSingleJid.initial_ping,
                "minions": ["minion0", "minion1", "minion2", "minion3"],
            }
        elif fun == "state.sls":
            MockPubSingleJid.calls += 1
            MockPubSingleJid.captured_jids.append(passed_jid)
            MockPubSingleJid.batch_tgts.append(list(tgt))
            # Use the passed JID if provided, otherwise generate one
            jid = passed_jid if passed_jid else salt.utils.jid.gen_jid({})
            pub_ret = {"jid": jid, "minions": tgt}
        elif fun == "saltutil.find_job":
            jid = salt.utils.jid.gen_jid({})
            pub_ret = {"jid": jid, "minions": tgt}
        return pub_ret


class MockSubscriberSingleJid:
    """
    Mock subscriber that returns results for all minions using the passed JIDs.
    """

    calls = 0
    pubret = None

    def __init__(self, *args, **kwargs):
        return

    def recv(self, timeout=None):
        if MockSubscriberSingleJid.pubret.initial_ping:
            jid = MockSubscriberSingleJid.pubret.initial_ping
            if MockSubscriberSingleJid.calls == 0:
                MockSubscriberSingleJid.calls += 1
                return self._ret(jid, minion_id="minion0", fun="test.ping")
            elif MockSubscriberSingleJid.calls == 1:
                MockSubscriberSingleJid.calls += 1
                return self._ret(jid, minion_id="minion1", fun="test.ping")
            elif MockSubscriberSingleJid.calls == 2:
                MockSubscriberSingleJid.calls += 1
                return self._ret(jid, minion_id="minion2", fun="test.ping")
            elif MockSubscriberSingleJid.calls == 3:
                MockSubscriberSingleJid.calls += 1
                return self._ret(jid, minion_id="minion3", fun="test.ping")

        captured = MockSubscriberSingleJid.pubret.captured_jids
        tgts = MockSubscriberSingleJid.pubret.batch_tgts

        if len(captured) >= 1 and MockSubscriberSingleJid.calls == 4:
            # First batch, first minion
            MockSubscriberSingleJid.calls += 1
            return self._ret(captured[0], minion_id=tgts[0][0], fun="state.sls")
        if len(captured) >= 1 and MockSubscriberSingleJid.calls == 5:
            # First batch, second minion
            MockSubscriberSingleJid.calls += 1
            return self._ret(captured[0], minion_id=tgts[0][1], fun="state.sls")
        if len(captured) >= 2 and MockSubscriberSingleJid.calls == 6:
            # Second batch, first minion
            MockSubscriberSingleJid.calls += 1
            return self._ret(captured[1], minion_id=tgts[1][0], fun="state.sls")
        if len(captured) >= 2 and MockSubscriberSingleJid.calls == 7:
            # Second batch, second minion
            MockSubscriberSingleJid.calls += 1
            return self._ret(captured[1], minion_id=tgts[1][1], fun="state.sls")
        return

    def _ret(self, jid, minion_id, fun, _return=True, _retcode=0):
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


def test_batch_single_jid():
    """
    Test that batch mode uses a single JID for all batch iterations.
    4 minions, batch size 2 → 2 iterations, same JID.
    """
    # Reset class state
    MockPubSingleJid.calls = 0
    MockPubSingleJid.initial_ping = False
    MockPubSingleJid.captured_jids = []
    MockPubSingleJid.batch_tgts = []
    MockSubscriberSingleJid.calls = 0
    MockSubscriberSingleJid.pubret = None

    mock_pub = MockPubSingleJid()
    MockSubscriberSingleJid.pubret = mock_pub

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
    }
    with patch("salt.transport.tcp.PublishClient", MockSubscriberSingleJid):
        batch = salt.cli.batch.Batch(opts, quiet=True)
        with patch.object(batch.local, "pub", Mock(side_effect=mock_pub)):
            with patch.object(
                batch.local, "returns_for_job", Mock(side_effect=returns_for_job)
            ):
                ret = list(batch.run())

    # All 4 minions should return results
    assert len(ret) == 4
    for val, _ in ret:
        values = list(val.values())
        assert len(values) == 1
        assert values[0] is True

    # Both batch iterations should have received the same JID
    assert len(mock_pub.captured_jids) == 2
    assert mock_pub.captured_jids[0] == mock_pub.captured_jids[1]
    assert mock_pub.captured_jids[0] != ""


def test_batch_single_jid_job_cache_merge(tmp_path):
    """
    Scenario test: batch produces a single JID, and the job cache accumulates
    all minions from every batch iteration under that JID.

    Exercises batch.run() → single JID generation, then simulates what the
    master does after each pub (save_load + save_minions per iteration), and
    finally verifies get_load returns the complete union of minions.
    """
    # Reset class state
    MockPubSingleJid.calls = 0
    MockPubSingleJid.initial_ping = False
    MockPubSingleJid.captured_jids = []
    MockPubSingleJid.batch_tgts = []
    MockSubscriberSingleJid.calls = 0
    MockSubscriberSingleJid.pubret = None

    mock_pub = MockPubSingleJid()
    MockSubscriberSingleJid.pubret = mock_pub

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
    }

    # Phase 1: Run batch, capture the single JID and per-iteration targets
    with patch("salt.transport.tcp.PublishClient", MockSubscriberSingleJid):
        batch = salt.cli.batch.Batch(opts, quiet=True)
        with patch.object(batch.local, "pub", Mock(side_effect=mock_pub)):
            with patch.object(
                batch.local, "returns_for_job", Mock(side_effect=returns_for_job)
            ):
                ret = list(batch.run())

    assert len(ret) == 4
    assert len(mock_pub.captured_jids) == 2
    batch_jid = mock_pub.captured_jids[0]
    assert batch_jid == mock_pub.captured_jids[1]

    # Phase 2: Simulate what the master does after each pub — call
    # save_load once (first iteration) then save_minions per iteration.
    cache_dir = str(tmp_path / "cache")
    cache_opts = {"cachedir": cache_dir, "hash_type": "sha256"}

    clear_load = {
        "fun": "state.sls",
        "jid": batch_jid,
        "tgt": "",
        "tgt_type": "list",
        "user": "root",
    }

    with patch.object(local_cache, "__opts__", cache_opts, create=True):
        local_cache.save_load(batch_jid, clear_load)
        for tgt_list in mock_pub.batch_tgts:
            local_cache.save_minions(batch_jid, tgt_list)

        # Phase 3: Verify get_load returns the complete union
        result = local_cache.get_load(batch_jid)

    all_minions = set()
    for tgt_list in mock_pub.batch_tgts:
        all_minions.update(tgt_list)

    assert result["jid"] == batch_jid
    assert result["Minions"] == sorted(all_minions)
    assert len(result["Minions"]) == 4
