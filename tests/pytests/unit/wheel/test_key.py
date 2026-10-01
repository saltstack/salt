"""
Unit tests for the ``key`` wheel module (#63477): accept/reject/delete and
their ``_dict`` variants must report ``success=False`` when the match names no
key the command can act on or leave in its target state, while re-asserting a
key already in its target state stays an idempotent success.
"""

import os

import pytest

import salt.config
import salt.crypt
import salt.wheel
import salt.wheel.key
from tests.support.mock import MagicMock, patch


@pytest.fixture
def context():
    return {}


def _run(func, context, glob_match_result, *args, **kwargs):
    """
    Call a wheel key function with ``salt.key.get_key`` mocked so ``glob_match``
    returns ``glob_match_result`` and ``__context__`` bound to ``context``. For
    the ``_dict`` variants pass the match dict as the positional arg (they use
    it directly and never call ``glob_match``).
    """
    skey = MagicMock()
    skey.ACC, skey.PEND, skey.REJ, skey.DEN = (
        "minions",
        "minions_pre",
        "minions_rejected",
        "minions_denied",
    )
    skey.glob_match.return_value = glob_match_result
    cm = MagicMock()
    cm.__enter__.return_value = skey
    cm.__exit__.return_value = False
    with patch("salt.key.get_key", return_value=cm), patch.object(
        salt.wheel.key, "__context__", context, create=True
    ), patch.object(salt.wheel.key, "__opts__", {}, create=True):
        func(*args, **kwargs)
    return skey


def _rc(context):
    return context.get("retcode", 0)


# --- a non-existent key (no match anywhere) always fails ---------------------


@pytest.mark.parametrize("func", ["accept", "reject", "delete"])
def test_glob_no_match_sets_retcode(context, func):
    _run(getattr(salt.wheel.key, func), context, {}, "invalid-minion")
    assert _rc(context) == 1


# --- a key already in the target state stays an idempotent success -----------


def test_accept_pending_no_retcode(context):
    _run(salt.wheel.key.accept, context, {"minions_pre": ["web1"]}, "web1")
    assert _rc(context) == 0


def test_accept_already_accepted_is_idempotent(context):
    _run(salt.wheel.key.accept, context, {"minions": ["web1"]}, "web1")
    assert _rc(context) == 0


def test_reject_already_rejected_is_idempotent(context):
    _run(salt.wheel.key.reject, context, {"minions_rejected": ["web1"]}, "web1")
    assert _rc(context) == 0


def test_delete_match_any_state_no_retcode(context):
    _run(salt.wheel.key.delete, context, {"minions": ["web1"]}, "web1")
    assert _rc(context) == 0


# --- a key only in a state the command will not touch is a failure -----------


def test_accept_rejected_key_without_include_sets_retcode(context):
    # rejected key + default include_rejected=False -> nothing accepted
    _run(salt.wheel.key.accept, context, {"minions_rejected": ["web1"]}, "web1")
    assert _rc(context) == 1


def test_accept_rejected_key_with_include_no_retcode(context):
    _run(
        salt.wheel.key.accept,
        context,
        {"minions_rejected": ["web1"]},
        "web1",
        include_rejected=True,
    )
    assert _rc(context) == 0


def test_reject_accepted_key_without_include_sets_retcode(context):
    # security-sharp: rejecting an accepted minion with default flags is a
    # no-op; it must not report success (the admin is not actually locking it
    # out).
    _run(salt.wheel.key.reject, context, {"minions": ["web1"]}, "web1")
    assert _rc(context) == 1


def test_reject_accepted_key_with_include_no_retcode(context):
    _run(
        salt.wheel.key.reject,
        context,
        {"minions": ["web1"]},
        "web1",
        include_accepted=True,
    )
    assert _rc(context) == 0


# --- the _dict variants get the same guard ----------------------------------


def test_accept_dict_empty_sets_retcode(context):
    _run(salt.wheel.key.accept_dict, context, {}, {})
    assert _rc(context) == 1


def test_accept_dict_pending_no_retcode(context):
    _run(salt.wheel.key.accept_dict, context, {}, {"minions_pre": ["web1"]})
    assert _rc(context) == 0


def test_accept_dict_rejected_without_include_sets_retcode(context):
    _run(salt.wheel.key.accept_dict, context, {}, {"minions_rejected": ["web1"]})
    assert _rc(context) == 1


def test_reject_dict_accepted_without_include_sets_retcode(context):
    _run(salt.wheel.key.reject_dict, context, {}, {"minions": ["web1"]})
    assert _rc(context) == 1


def test_delete_dict_empty_sets_retcode(context):
    _run(salt.wheel.key.delete_dict, context, {}, {})
    assert _rc(context) == 1


def test_delete_dict_any_state_no_retcode(context):
    _run(salt.wheel.key.delete_dict, context, {}, {"minions": ["web1"]})
    assert _rc(context) == 0


# --- the failure retcode must not leak across calls on a reused client -------


def test_retcode_does_not_leak_on_reused_client(tmp_path):
    """
    ``low()`` resets retcode per call, so a failure retcode set by a no-match
    ``key.accept`` on a reused ``WheelClient`` -- as used by the master's
    ``ClearFuncs.wheel_`` and the reactor's cached client -- does not poison a
    later successful call. Regression test for #63477.
    """
    pki = tmp_path / "pki"
    for sub in ("minions", "minions_pre", "minions_rejected", "minions_denied"):
        (pki / sub).mkdir(parents=True)
    salt.crypt.write_keys(str(pki / "minions_pre"), "pend1", 2048)
    os.replace(
        str(pki / "minions_pre" / "pend1.pub"), str(pki / "minions_pre" / "pend1")
    )
    os.remove(str(pki / "minions_pre" / "pend1.pem"))
    opts = salt.config.master_config(None)
    opts.update(
        pki_dir=str(pki),
        cachedir=str(tmp_path / "cache"),
        sock_dir=str(tmp_path / "sock"),
        key_logfile=str(tmp_path / "key.log"),
    )

    (tmp_path / "cache" / "proc").mkdir(parents=True)
    client = salt.wheel.WheelClient(opts)
    no_match = client.cmd(
        "key.accept", ["does-not-exist"], print_event=False, full_return=True
    )
    assert no_match["success"] is False
    # Same client: a genuinely successful accept must still report success.
    accepted = client.cmd("key.accept", ["pend1"], print_event=False, full_return=True)
    assert accepted["success"] is True
    assert accepted["return"] == {"minions": ["pend1"]}
