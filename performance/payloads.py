def received_at_rpc(jid: str, ts):
    return dict(message_type="job_received_at_rpc", ts=ts, meta=dict(jid=jid))


def enqueued(jid: str, ts):
    return dict(message_type="job_enqueued", ts=ts, meta=dict(jid=jid))


def taken_by_master(jid: str, master_id: str, ts):
    return dict(message_type="job_taken_by_master", ts=ts, meta=dict(jid=jid, master_id=master_id))


def taken_by_minion(jid: str, minion_id: str, ts):
    return dict(message_type="job_taken_by_minion", ts=ts, meta=dict(jid=jid, minion_id=minion_id))


def executed_by_minion(jid: str, minion_id: str, ts, return_size):
    return dict(message_type="job_fulfilled_by_minion", ts=ts,
                meta=dict(jid=jid, minion_id=minion_id, result_size_bytes=return_size))


def job_results_start(jid: str, ts):
    return dict(message_type="job_results_start", ts=ts,
                meta=dict(jid=jid))


def job_results_end(jid: str, master_id: str, ts):
    return dict(message_type="job_results_end", ts=ts,
                meta=dict(jid=jid, master_id=master_id, minions_expected=1, minions_returned=1))


def message_observed(msg_length: int, tag: str, ts):
    return dict(message_type="message_observed_in_queue", ts=ts,
                meta=dict(length=msg_length, tag=tag))
