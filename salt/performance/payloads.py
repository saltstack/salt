def received_at_rpc(jid, ts):
    return dict(message_type="job_received_at_rpc", ts=ts, meta=dict(jid=jid))


def enqueued(jid, ts):
    return dict(message_type="job_enqueued", ts=ts, meta=dict(jid=jid))


def taken_by_master(jid, master_id, ts):
    return dict(message_type="job_taken_by_master", ts=ts, meta=dict(jid=jid, master_id=master_id))


def taken_by_minion(jid, minion_id, ts):
    return dict(message_type="job_taken_by_minion", ts=ts, meta=dict(jid=jid, minion_id=minion_id))


def executed_by_minion(jid, minion_id, ts, return_size):
    return dict(message_type="job_fulfilled_by_minion", ts=ts,
                meta=dict(jid=jid, minion_id=minion_id, result_size_bytes=return_size))


def job_results_start(jid, ts):
    return dict(message_type="job_results_start", ts=ts,
                meta=dict(jid=jid))


def job_results_end(jid, master_id, ts, minions_expected, minions_returned):
    return dict(message_type="job_results_end", ts=ts,
                meta=dict(jid=jid, master_id=master_id, minions_expected=minions_expected,
                          minions_returned=minions_returned))


def job_return(jid, master_id, minion_id, ts):
    return dict(message_type="job_return", ts=ts,
                meta=dict(jid=jid, master_id=master_id, minion_id=minion_id))


def message_observed(master_id, msg_length, tag, ts):
    return dict(message_type="message_observed_in_queue", ts=ts,
                meta=dict(length=msg_length, tag=tag, master_id=master_id))
