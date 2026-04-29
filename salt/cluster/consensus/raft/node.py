"""
Raft node: elections, log replication callbacks, and peer RPC surface.

The :class:`Peer` / :class:`ManualPeer` boundary and
``register_schedule_timeout`` / ``register_peer_factory`` hooks keep transport
and timers out of the core algorithm.

This module is intentionally **not** asyncio-based: the core stays
synchronous with callbacks. Salt-side consensus glue should prefer asyncio
for I/O where we control it, and adapt into these callbacks.
"""

import functools
import json
import logging
import threading
import time

from salt.cluster.consensus.raft.log import Log, LogEntryType, MembershipStateMachine
from salt.cluster.consensus.raft.util import gettimeout

log = logging.getLogger(__name__)


class NoOpLock:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def acquire(self, *args, **kwargs):
        return True

    def release(self, *args, **kwargs):
        pass


NOOPLOCK = NoOpLock()


class CandidacyError(Exception):
    pass


class Vote:
    def __init__(self, voter_id, term, granted=False):
        self.voter_id = voter_id
        self.term = term
        self.granted = granted

    @property
    def node_id(self):
        return self.voter_id

    def info(self):
        return {"voter_id": self.voter_id, "term": self.term, "granted": self.granted}


class Peer:
    """Interface for interacting with a remote node."""

    def __init__(self, node, node_id=None, voting=True):
        """Initialize the peer with node and optional voting status."""
        self.node = node
        self._node_id = node_id or getattr(
            node, "node_id", getattr(node, "address", "mock")
        )
        self.voting = voting

    @property
    def address(self):
        """Return the network address of the peer."""
        return getattr(self.node, "address", self._node_id)

    @property
    def node_id(self):
        """Return the unique ID of the peer."""
        return self._node_id

    def request_vote(self, callback, node_id, term, last_log_term, last_log_index):
        """Issue a RequestVote RPC."""
        granted, our_term, lc_addr = self.node.request_vote(
            node_id, term, last_log_term=last_log_term, last_log_index=last_log_index
        )
        if callback:
            callback(self.node_id, granted, our_term)

    def pre_request_vote(self, callback, node_id, term, last_log_term, last_log_index):
        """Issue a Pre-RequestVote RPC."""
        granted, our_term, lc_addr = self.node.pre_request_vote(
            node_id, term, last_log_term=last_log_term, last_log_index=last_log_index
        )
        if callback:
            callback(self.node_id, granted, our_term)

    def append_entries(
        self,
        callback,
        leader_id,
        term,
        prev_log_term,
        prev_log_index,
        leader_commit,
        *entries,
        **kwargs,
    ):
        """Issue an AppendEntries RPC."""
        # Convert *entries to a list for the target method
        actual_entries = list(entries)

        success, our_term, last_idx, conflict_term, lc_addr = self.node.append_entries(
            leader_id,
            term,
            prev_log_term,
            prev_log_index,
            leader_commit,
            *actual_entries,
            **kwargs,
        )
        if callback:
            # Term, prev_log_term, prev_log_index, sent_log_index, node_id, ourterm, success, conflict_index, conflict_term, *entries
            sent_log_index = (
                prev_log_index + len(actual_entries)
                if prev_log_index is not None
                else len(actual_entries) - 1
            )
            callback(
                term,
                prev_log_term,
                prev_log_index,
                sent_log_index,
                self.node_id,
                our_term,
                success,
                last_idx,  # conflict_index or last_index
                conflict_term,
                *actual_entries,
            )

    def install_snapshot(
        self,
        callback,
        leader_id,
        term,
        last_included_index,
        last_included_term,
        data,
        **kwargs,
    ):
        """Issue an InstallSnapshot RPC."""
        our_term, lc_addr = self.node.install_snapshot(
            leader_id, term, last_included_index, last_included_term, data, **kwargs
        )
        if callback:
            callback(self.node_id, our_term)


class ManualPeer:
    """Mock peer for unit tests that queues requests."""

    def __init__(self, node, node_id=None, voting=True):
        self.node = node
        self.node_id = node_id or getattr(node, "node_id", "mock")
        self.address = getattr(node, "address", self.node_id)
        self.voting = voting
        self.requests = []

    def request_vote(
        self, callback, candidate_id, term, last_log_term=None, last_log_index=None
    ):
        self.requests.append(
            ("rv", candidate_id, term, callback, last_log_term, last_log_index)
        )

    def pre_request_vote(
        self, callback, candidate_id, term, last_log_term=None, last_log_index=None
    ):
        self.requests.append(
            ("prv", candidate_id, term, callback, last_log_term, last_log_index)
        )

    def append_entries(
        self,
        callback,
        leader_id,
        term,
        prev_log_term,
        prev_log_index,
        leader_commit,
        *entries,
        **kwargs,
    ):
        self.requests.append(
            (
                "ae",
                leader_id,
                term,
                callback,
                prev_log_index,
                prev_log_term,
                leader_commit,
                list(entries),
                kwargs.get("leader_client_address"),
            )
        )

    def install_snapshot(
        self,
        callback,
        leader_id,
        term,
        last_included_index,
        last_included_term,
        data,
        **kwargs,
    ):
        self.requests.append(
            (
                "is",
                leader_id,
                term,
                callback,
                last_included_index,
                last_included_term,
                data,
            )
        )

    def handle_all_requests(self):
        while self.requests:
            req = self.requests.pop(0)
            kind = req[0]
            if kind == "rv":
                # candidate_id, term, callback, last_log_term, last_log_index
                res = self.node.request_vote(
                    req[1], req[2], last_log_term=req[4], last_log_index=req[5]
                )
                req[3](self.node_id, res[0], res[1])
            elif kind == "prv":
                # candidate_id, term, callback, last_log_term, last_log_index
                res = self.node.pre_request_vote(
                    req[1], req[2], last_log_term=req[4], last_log_index=req[5]
                )
                req[3](self.node_id, res[0], res[1])
            elif kind == "ae":
                # leader_id, term, callback, prev_log_index, prev_log_term, leader_commit, entries, lc_addr
                res = self.node.handle_append_entries(
                    req[1],
                    req[2],
                    req[5],
                    req[4],
                    req[6],
                    *req[7],
                    leader_client_address=req[8],
                )
                sent_log_index = (
                    req[4] + len(req[7]) if req[4] is not None else len(req[7]) - 1
                )
                req[3](
                    req[2],
                    req[5],
                    req[4],
                    sent_log_index,
                    self.node_id,
                    res[1],
                    res[0],
                    res[2],
                    res[3],
                    *req[7],
                )
            elif kind == "is":
                # leader_id, term, callback, last_index, last_term, data
                res = self.node.install_snapshot(req[1], req[2], req[4], req[5], req[6])
                req[3](self.node_id, res[0])

    def drop_requests(self):
        self.requests = []


def lock(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return func(self, *args, **kwargs)

    return wrapper


class NodeState:
    START = "start"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

    def __init__(self):
        self._state = self.START

    def become_candidate(self):
        if self._state == self.START:
            raise RuntimeError("State must be follower first")
        if self._state != self.FOLLOWER and self._state != self.CANDIDATE:
            raise RuntimeError("Not follower")
        self._state = self.CANDIDATE

    def become_leader(self):
        if self._state == self.START:
            raise RuntimeError("State must be follower first")
        if self._state != self.CANDIDATE and self._state != self.LEADER:
            raise RuntimeError(f"Not candidate ({self._state})")
        self._state = self.LEADER

    def become_follower(self):
        self._state = self.FOLLOWER

    def __str__(self):
        return self._state

    def __repr__(self):
        return f"<NodeState('{self._state}') at {id(self)} >"

    def __eq__(self, other):
        if isinstance(other, str):
            return self._state == other
        return self._state == getattr(other, "_state", None)


class Candidacy:
    def __init__(self, term, peers):
        self.term = term
        self.peers = set(peers)
        self.votes = {}

    def handle_reply(self, node_id, term, result):
        if term != self.term:
            raise CandidacyError(f"Term {term} does not match ours {self.term}")
        if node_id not in self.peers:
            raise CandidacyError(f"{node_id} is not a peer")
        if node_id in self.votes:
            raise CandidacyError(f"Already received a reply from this peer: {node_id}")
        self.votes[node_id] = bool(result)

    def elected(self):
        v_votes = [v for v in self.votes.values() if v is True]
        # Include self
        return (len(v_votes) + 1) >= (len(self.peers) + 1) // 2 + 1


class Node:
    def __init__(
        self,
        address,
        storage=None,
        peers=None,
        _follower_min=150,
        _follower_max=300,
        _candidate_min=150,
        _candidate_max=300,
        _leader_beacon_min=50,
        _leader_beacon_max=100,
        state_machine=None,
        membership_sm=None,
        max_log_size=None,
        voting=True,
        **kwargs,
    ):
        self.address = address
        self.node_id = kwargs.get("node_id", address)
        self.client_address = kwargs.get("client_address")
        self.peers = peers or []
        self.storage = storage
        # True if this node participates in quorum; False means learner/observer.
        self.voting = voting

        # Use local variable to avoid property collision
        sm = state_machine or (
            getattr(self.storage, "state_machine", None) if storage else None
        )
        self.log = Log(storage=storage, state_machine=sm, max_log_size=max_log_size)

        # Membership state machine: applies CONFIG entries to track the committed
        # voter/learner sets.  It is the authoritative query store for committed
        # membership; it does NOT drive on_config_change (that is called directly
        # from apply_entries so the eager log_add path and commit path stay in sync).
        if membership_sm is None:
            membership_sm = MembershipStateMachine()
        self.membership_sm = membership_sm

        self.state = NodeState()
        self._term = 0
        self._voted_for = None
        self.vote = None
        self.leader = None
        self.leader_client_address_map = {}

        self._follower_min = _follower_min
        self._follower_max = _follower_max
        self._candidate_min = _candidate_min
        self._candidate_max = _candidate_max
        self._leader_beacon_min = _leader_beacon_min
        self._leader_beacon_max = _leader_beacon_max

        self._lock = kwargs.get("_lock", NOOPLOCK)
        self._schedule_timeout_method = None
        self._peer_factory = None

        self.last_followed = self.get_now()
        self._follower_timeout = None
        self._candidate_timeout = None
        self._leader_beacon_timeout = None

        self._pre_candidacy = None
        self.candidacy = None
        self.native_engine = None

        self.next_index = {}
        self.match_index = {}
        self._applied_config_index = -1  # index of the most recently applied CONFIG

        if storage:
            st = storage.load_state()
            if isinstance(st, dict):
                self._term = st.get("term", 0)
                self._voted_for = st.get("voted_for")
            else:
                self._term, self._voted_for = st
            if self._voted_for:
                self.vote = Vote(self._voted_for, self._term, granted=True)

    @property
    def term(self):
        return self._term

    @term.setter
    def term(self, val):
        if val != self._term:
            self._term = val
            if self.storage:
                self.storage.save_state(self._term, self._voted_for)

    @property
    def voted_for(self):
        return self._voted_for

    @voted_for.setter
    def voted_for(self, val):
        if val != self._voted_for:
            self._voted_for = val
            if self.storage:
                self.storage.save_state(self._term, self._voted_for)

    @property
    def vote(self):
        if self._voted_for:
            return Vote(self._voted_for, self.term, granted=True)
        return None

    @vote.setter
    def vote(self, val):
        if val:
            self.voted_for = val.voter_id
        else:
            self.voted_for = None

    @property
    def follower_timeout(self):
        return getattr(self, "_follower_timeout_val", None)

    @property
    def leader_beacon_timeout(self):
        return getattr(self, "_leader_timeout_val", None)

    @property
    def candidate_timeout(self):
        return getattr(self, "_candidate_timeout_val", None)

    def get_now(self):
        if self._schedule_timeout_method:
            scheduler = getattr(self._schedule_timeout_method, "__self__", None)
            if scheduler and hasattr(scheduler, "time"):
                return scheduler.time
        return time.monotonic()

    def register_schedule_timeout(self, method):
        self._schedule_timeout_method = method

    def register_peer_factory(self, factory):
        self._peer_factory = factory

    def register_membership_sm(self, sm):
        """
        Replace the membership state machine.

        The SM is the authoritative query store for committed membership
        (``current_voters()``, ``current_learners()``).  Side-effects on
        ``Node.peers`` / ``Node.voting`` are driven directly by
        ``apply_entries`` → ``on_config_change``, not by the SM's
        ``on_change`` callback, to avoid double-applying eager leader updates.
        """
        self.membership_sm = sm

    def schedule_timeout(self, delay, callback):
        if not self._schedule_timeout_method:
            raise RuntimeError("Register a scheduling method first")
        return self._schedule_timeout_method(delay, callback)

    @lock
    def become_candidate(self):
        self.state.become_candidate()
        self.term += 1
        log.info("Node %s BECOMING CANDIDATE for term %s", self.node_id, self.term)
        self.voted_for = self.node_id
        self.last_followed = self.get_now()

        voters = [p.node_id for p in self.peers if getattr(p, "voting", True)]
        self.candidacy = Candidacy(self.term, voters)

        timeout = gettimeout(self._candidate_min, self._candidate_max)
        self._candidate_timeout_val = timeout
        if self._candidate_timeout:
            self._candidate_timeout.cancel()
        self._candidate_timeout = self.schedule_timeout(timeout, self.become_candidate)

        if not voters:
            self.become_leader()
        else:
            last_log_term = self.log.last_term
            last_log_index = self.log.index
            for peer in self.peers:
                if getattr(peer, "voting", True):
                    peer.request_vote(
                        self.request_vote_reply,
                        self.node_id,
                        self.term,
                        last_log_term,
                        last_log_index,
                    )

    def request_votes(self):
        """Helper for tests or manual triggers."""
        if self.state != NodeState.CANDIDATE:
            raise RuntimeError("Not a candidate")
        # Reuse logic from become_candidate or just trigger RPCs
        last_log_term = self.log.last_term
        last_log_index = self.log.index
        for peer in self.peers:
            if getattr(peer, "voting", True):
                peer.request_vote(
                    self.request_vote_reply,
                    self.node_id,
                    self.term,
                    last_log_term,
                    last_log_index,
                )

    @lock
    def request_vote_reply(self, peer_id, granted, term):
        if term > self.term:
            self.become_follower(term)
            return

        if (
            self.state != NodeState.CANDIDATE
            or not self.candidacy
            or self.candidacy.term != term
        ):
            return

        self.candidacy.handle_reply(peer_id, term, granted)
        if self.candidacy.elected():
            self.become_leader()

    @lock
    def become_leader(self):
        self.state.become_leader()
        log.info("Node %s BECOMING LEADER for term %s", self.node_id, self.term)
        self.leader = self.node_id
        if self._candidate_timeout:
            self._candidate_timeout.cancel()
        self._candidate_timeout = None

        if self.native_engine:
            self.native_engine.become_leader(self.term)

        self.next_index = {p.node_id: self.log.index + 1 for p in self.peers}
        self.match_index = {p.node_id: -1 for p in self.peers}
        self.schedule_heartbeat()

    def schedule_heartbeat(self):
        with self._lock:
            if self.state == NodeState.LEADER:
                self.leader_beacon()
                timeout = gettimeout(self._leader_beacon_min, self._leader_beacon_max)
                self._leader_timeout_val = timeout
                if self._leader_beacon_timeout:
                    self._leader_beacon_timeout.cancel()
                self._leader_beacon_timeout = self.schedule_timeout(
                    timeout, self.schedule_heartbeat
                )

    def leader_beacon(self):
        for peer in self.peers:
            if self.native_engine:
                peer.send_heartbeat(self.term, self.commit_index)
            else:
                self.send_append_entries(peer, entries=[])

    def send_append_entries(self, peer, entries=None):
        ni = self.next_index.get(peer.node_id, self.log.index + 1)
        prev_idx = ni - 1
        prev_entry = self.log.get(prev_idx)
        prev_term = prev_entry.term if prev_entry else self.log.last_included_term

        if entries is None:
            entries = [e for e in self.log.entries if e.index >= ni]

        peer.append_entries(
            self.append_entries_reply,
            self.node_id,
            self.term,
            prev_term,
            prev_idx,
            self.log.commit_index,
            *entries,
            leader_client_address=self.client_address,
        )

    @lock
    def append_entries_reply(
        self,
        sent_term,
        sent_prev_term,
        sent_prev_index,
        sent_log_index,
        peer_id,
        term,
        success,
        *args,
    ):
        if term > self.term:
            self.become_follower(term)
            return

        if self.state != NodeState.LEADER:
            return

        if success:
            self.match_index[peer_id] = max(
                self.match_index.get(peer_id, -1), sent_log_index
            )
            self.next_index[peer_id] = self.match_index[peer_id] + 1

            # Learner promotion: once a learner has caught up to the leader's
            # log, propose a CONFIG entry to promote it.  The peer stays
            # non-voting until that entry is *applied* (see apply_entries).
            for p in self.peers:
                if p.node_id == peer_id and not p.voting:
                    if self.match_index[peer_id] >= self.log.index:
                        voters = (
                            [self.node_id]
                            + [px.node_id for px in self.peers if px.voting]
                            + [peer_id]
                        )
                        learners = [
                            px.node_id
                            for px in self.peers
                            if not px.voting and px.node_id != peer_id
                        ]
                        self.log_add(
                            {"voters": voters, "learners": learners},
                            entry_type=LogEntryType.CONFIG,
                        )

            self.advance_commit_index()
        else:
            self.next_index[peer_id] = max(0, self.next_index.get(peer_id, 1) - 1)

    def advance_commit_index(self):
        matches = sorted([m for m in self.match_index.values()] + [self.log.index])
        voters = [p for p in self.peers if getattr(p, "voting", True)]
        quorum = (len(voters) + 1) // 2 + 1
        if len(matches) >= quorum:
            q_idx = matches[-quorum]
            if q_idx > self.log.commit_index:
                entry = self.log.get(q_idx)
                if entry and entry.term == self.term:
                    self.log.commit(q_idx)
                    self.apply_entries()

    def apply_entries(self):
        while self.log.last_applied < self.log.commit_index:
            new_applied = self.log.last_applied + 1
            entry = self.log.get(new_applied)
            if entry:
                if entry.type == LogEntryType.COMMAND:
                    if self.state_machine:
                        self.state_machine.apply(
                            entry.cmd,
                            client_id=entry.client_id,
                            sequence_num=entry.sequence_num,
                        )
                elif entry.type == LogEntryType.CONFIG:
                    cmd = entry.cmd
                    voters = cmd.get("voters", []) if isinstance(cmd, dict) else cmd
                    learners = cmd.get("learners", []) if isinstance(cmd, dict) else []
                    # Always update the SM's committed view (query authority).
                    if self.membership_sm is not None:
                        self.membership_sm.apply(cmd, index=entry.index)
                    # Only call on_config_change when this committed entry is
                    # strictly newer than what the eager log_add path already
                    # applied.  This prevents an older committed CONFIG from
                    # clobbering a newer CONFIG that the leader optimistically
                    # applied to its peer list when it wrote the entry.
                    if entry.index >= self._applied_config_index:
                        self._applied_config_index = entry.index
                        self.on_config_change(voters, learners)
            self.log.last_applied = new_applied

    @lock
    def become_follower(self, term=None):
        if term is not None:
            if term < self.term:
                raise RuntimeError("Term lower than ours")
            if term > self.term:
                self.term = term
                self.voted_for = None

        self.state.become_follower()
        self.leader = None
        log.info("Node %s BECOMING FOLLOWER for term %s", self.node_id, self.term)

        self._pre_candidacy = None
        self.candidacy = None

        if self._leader_beacon_timeout:
            self._leader_beacon_timeout.cancel()
        self._leader_beacon_timeout = None

        if self.native_engine:
            self.native_engine.become_follower(self.term)

        self.last_followed = self.get_now()
        self.schedule_follower_timeout()

    def schedule_follower_timeout(self):
        if self._follower_timeout:
            self._follower_timeout.cancel()
        timeout = gettimeout(self._follower_min, self._follower_max)
        self._follower_timeout_val = timeout

        def _cb():
            self._follower_timeout = None
            self.follower_timeout_callback()

        self._follower_timeout = self.schedule_timeout(timeout, _cb)

    def follower_timeout_callback(self):
        with self._lock:
            if self.state == NodeState.FOLLOWER:
                now = self.get_now()
                if now - self.last_followed < self._follower_min * 0.001:
                    self.schedule_follower_timeout()
                    return
                if not self.voting:
                    # Learner/observer — reset the timer and wait for promotion.
                    self.schedule_follower_timeout()
                    return
                self.start_pre_vote()

    @lock
    def start_pre_vote(self):
        if self.state != NodeState.FOLLOWER:
            return
        voters = [p.node_id for p in self.peers if getattr(p, "voting", True)]
        if not voters:
            self.become_candidate()
            return
        self._pre_candidacy = Candidacy(self.term + 1, voters)
        last_log_term = self.log.last_term
        last_log_index = self.log.index
        for peer in self.peers:
            if getattr(peer, "voting", True):
                peer.pre_request_vote(
                    self.pre_request_vote_reply,
                    self.node_id,
                    self.term + 1,
                    last_log_term,
                    last_log_index,
                )

    @lock
    def pre_request_vote_reply(self, peer_id, granted, term):
        if term > self.term + 1:
            self.become_follower(term - 1)
            return
        if self.state == NodeState.FOLLOWER and self._pre_candidacy:
            # Tests might pass older term (e.g. 0 when we pre-vote for 1)
            # We care about whether the vote is granted for OUR current pre-vote attempt
            self._pre_candidacy.handle_reply(peer_id, self._pre_candidacy.term, granted)
            if self._pre_candidacy.elected():
                self._pre_candidacy = None
                self.become_candidate()

    @lock
    def pre_request_vote(
        self, address, term, last_log_term=None, last_log_index=None, **kwargs
    ):
        llt = last_log_term if last_log_term is not None else kwargs.get("last_term")
        lli = last_log_index if last_log_index is not None else kwargs.get("last_index")

        if term > self.term + 1:
            self.term = term
            self.become_follower()
        now = self.get_now()
        lease_active = (now - self.last_followed) < self._follower_min * 0.001

        llt_val = llt if llt is not None else 0
        lli_val = lli if lli is not None else -1
        log_ok = llt_val > self.log.last_term or (
            llt_val == self.log.last_term and lli_val >= self.log.index
        )

        granted = (term == self.term + 1) and log_ok and not lease_active
        return granted, self.term, self.leader_client_address

    @lock
    def request_vote(
        self, address, term, last_log_term=None, last_log_index=None, **kwargs
    ):
        llt = last_log_term if last_log_term is not None else kwargs.get("last_term")
        lli = last_log_index if last_log_index is not None else kwargs.get("last_index")

        if term > self.term:
            self.become_follower(term)

        now = self.get_now()
        my_last_term = self.log.last_term
        my_last_index = self.log.index
        llt_val = llt if llt is not None else 0
        lli_val = lli if lli is not None else -1
        log_ok = llt_val > my_last_term or (
            llt_val == my_last_term and lli_val >= my_last_index
        )

        granted = (
            (term == self.term)
            and (self.voted_for is None or self.voted_for == address)
            and log_ok
        )

        if granted:
            self.voted_for = address
            self.last_followed = now
        return granted, self.term, self.leader_client_address

    @lock
    def handle_append_entries(
        self,
        leader_id,
        term,
        prev_log_term,
        prev_log_index,
        leader_commit,
        *entries,
        **kwargs,
    ):
        if term < self.term:
            return (
                False,
                self.term,
                self.log.index,
                self.term,
                self.leader_client_address,
            )
        if term > self.term:
            self.term = term

        self.state.become_follower()
        self.leader = leader_id
        self.last_followed = self.get_now()
        self.schedule_follower_timeout()

        lca = kwargs.get("leader_client_address")
        if lca:
            self.leader_client_address_map[leader_id] = lca

        # Log matching
        if prev_log_index >= 0:
            e = self.log.get(prev_log_index)
            if not e or e.term != prev_log_term:
                return (
                    False,
                    self.term,
                    self.log.index,
                    self.term,
                    self.leader_client_address,
                )

        curr_idx = prev_log_index + 1
        for entry in entries:
            # Handle normalized entry formats (LogEntry, tuple/list, or _asdict() dict)
            if isinstance(entry, dict):
                e_term = entry.get("term", self.term)
                e_cmd = entry.get("cmd", entry)
                e_type = entry.get("type", LogEntryType.COMMAND)
            else:
                e_term = getattr(
                    entry,
                    "term",
                    entry[0] if isinstance(entry, (list, tuple)) else self.term,
                )
                e_cmd = getattr(
                    entry,
                    "cmd",
                    entry[2] if isinstance(entry, (list, tuple)) else entry,
                )
                e_type = getattr(
                    entry,
                    "type",
                    (
                        entry[4]
                        if isinstance(entry, (list, tuple))
                        else LogEntryType.COMMAND
                    ),
                )

            # Use log.add with explicit index to trigger conflict detection and truncation
            self.log.add(e_term, e_cmd, index=curr_idx, entry_type=e_type)

            if e_type == LogEntryType.CONFIG:
                voters = e_cmd.get("voters", []) if isinstance(e_cmd, dict) else e_cmd
                learners = e_cmd.get("learners", []) if isinstance(e_cmd, dict) else []
                self._applied_config_index = curr_idx
                self.on_config_change(voters, learners=learners)

            curr_idx += 1

        if leader_commit > self.log.commit_index:
            self.log.commit(min(leader_commit, self.log.index))
            self.apply_entries()

        return True, self.term, self.log.index, self.term, self.leader_client_address

    def append_entries(self, *args, **kwargs):
        return self.handle_append_entries(*args, **kwargs)

    @lock
    def log_add(
        self, data, entry_type=LogEntryType.COMMAND, client_id=None, sequence_num=None
    ):
        if self.state != NodeState.LEADER:
            raise NotLeader()
        index = self.log.append(
            self.term,
            data,
            entry_type=entry_type,
            client_id=client_id,
            sequence_num=sequence_num,
        )
        if entry_type == LogEntryType.CONFIG:
            voters = data.get("voters", []) if isinstance(data, dict) else data
            learners = data.get("learners", []) if isinstance(data, dict) else []
            self._applied_config_index = index
            self.on_config_change(voters, learners=learners)
        for peer in self.peers:
            self.send_append_entries(peer)
        return index

    def append(self, data, client_id=None, sequence_num=None):
        return self.log_add(data, client_id=client_id, sequence_num=sequence_num)

    def on_config_change(self, voters, learners=None):
        # Update this node's own voting status.
        if voters and self.node_id in voters:
            self.voting = True
        elif learners and self.node_id in learners:
            self.voting = False

        if self._peer_factory:
            new_peers = []
            existing_peers = {p.node_id: p for p in self.peers}

            for addr in voters:
                if addr != self.node_id:
                    if addr in existing_peers:
                        p = existing_peers[addr]
                        p.voting = True
                        new_peers.append(p)
                    else:
                        new_peers.append(self._peer_factory(addr, voting=True))
            for addr in learners or []:
                if addr != self.node_id:
                    if addr in existing_peers:
                        p = existing_peers[addr]
                        p.voting = False
                        new_peers.append(p)
                    else:
                        new_peers.append(self._peer_factory(addr, voting=False))
            self.peers = new_peers
        else:
            # No factory — update voting flags on existing peers in-place.
            voter_set = set(voters or [])
            learner_set = set(learners or [])
            for p in self.peers:
                if p.node_id in voter_set:
                    p.voting = True
                elif p.node_id in learner_set:
                    p.voting = False

    def info(self):
        with self._lock:
            info = {
                "node_id": self.node_id,
                "address": self.address,
                "term": self.term,
                "state": str(self.state),
                "voting": self.voting,
                "leader": self.leader,
                "leader_client_address": self.leader_client_address,
                "last_index": self.log.index,
                "commit_index": self.log.commit_index,
                "last_applied": self.log.last_applied,
            }
            if self.membership_sm is not None:
                info["membership"] = {
                    "voters": self.membership_sm.current_voters(),
                    "learners": self.membership_sm.current_learners(),
                    "version": self.membership_sm.membership_version,
                }
            return info

    @property
    def leader_client_address(self):
        if self.state == NodeState.LEADER:
            return self.client_address
        return self.leader_client_address_map.get(self.leader)

    def install_snapshot(self, leader_id, term, last_index, last_term, data, **kwargs):
        with self._lock:
            if term < self.term:
                return self.term, self.leader_client_address
            self.term = term
            self.become_follower()
            self.leader = leader_id
            self.last_followed = self.get_now()
            self.schedule_follower_timeout()

            if self.log.last_included_index >= last_index:
                return self.term, self.node_id

            # Keep entries that follow the snapshot
            self.log.entries = [e for e in self.log.entries if e.index > last_index]
            self.log.last_included_index = last_index
            self.log.last_included_term = last_term

            if self.state_machine:
                # Handle bytes vs dict
                sd = (
                    data
                    if not isinstance(data, (bytes, memoryview))
                    else json.loads(data.decode())
                )
                self.state_machine.restore_snapshot(sd)

            self.log.commit_index = max(self.log.commit_index, last_index)
            self.log.last_applied = max(self.log.last_applied, last_index)
            self.apply_entries()
            return self.term, self.node_id

    @lock
    def install_snapshot_reply(self, peer_id, term):
        if term > self.term:
            self.become_follower(term)

    def candidacy_timeout_callback(self, candidacy):
        with self._lock:
            if self.state == NodeState.CANDIDATE and self.candidacy == candidacy:
                if candidacy.term < self.term:
                    self.candidacy = None
                else:
                    self.become_candidate()
            elif self.candidacy and self.candidacy == candidacy:
                self.candidacy = None

    def __repr__(self):
        return f"<Node('{self.address}') at {id(self)} >"

    @property
    def commit_index(self):
        return self.log.commit_index

    @commit_index.setter
    def commit_index(self, val):
        self.log.commit_index = val
        self.apply_entries()

        # Check if we should snapshot now that commit_index advanced and entries were applied
        if self.log.max_log_size and len(self.log.entries) >= self.log.max_log_size:
            if self.log.entries and self.log.commit_index >= self.log.entries[0].index:
                self.log.snapshot()

    @property
    def last_applied(self):
        return self.log.last_applied

    @last_applied.setter
    def last_applied(self, val):
        self.log.last_applied = val

    @property
    def state_machine(self):
        return self.log.state_machine


class NotLeader(Exception):
    pass


class LockingNode(Node):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("_lock", threading.RLock())
        super().__init__(*args, **kwargs)
