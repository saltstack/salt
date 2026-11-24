"""
Verify that a ``no_log: True`` state redacts log records emitted by the
state body itself -- not just the returned name/comment/changes.

This exercises the ``_no_log_scope`` context manager added in
``salt/state.py``.
"""

import logging

import pytest

from salt.state import _no_log_scope


@pytest.fixture
def state_logger():
    """A ``salt.states.*`` logger that the scrub filter is scoped to."""
    log = logging.getLogger("salt.states.test_no_log_widened")
    log.setLevel(logging.DEBUG)
    return log


class TestNoLogScope:
    def test_scrubs_debug_from_state_body(self, state_logger, caplog):
        """
        A fake state body emits ``log.debug("secret is %s", pillar_val)``
        while ``no_log: True``.  The captured record must have its
        pillar value scrubbed.
        """
        low = {"no_log": True}
        pillar_val = "super-secret-password"
        with caplog.at_level(logging.DEBUG, logger="salt.states.test_no_log_widened"):
            with _no_log_scope(low):
                state_logger.debug("secret is %s", pillar_val)

        # The emitted format includes the msg + args; after filter runs
        # msg is "**********" and args == ().
        for record in caplog.records:
            assert pillar_val not in record.getMessage()
        # And the formatted message is the placeholder
        placeholder_records = [
            r for r in caplog.records if "**********" in r.getMessage()
        ]
        assert placeholder_records, "expected at least one scrubbed record"

    def test_info_also_scrubbed(self, state_logger, caplog):
        low = {"no_log": True}
        pillar_val = "another-secret"
        with caplog.at_level(logging.INFO, logger="salt.states.test_no_log_widened"):
            with _no_log_scope(low):
                state_logger.info("got %s from pillar", pillar_val)

        for record in caplog.records:
            assert pillar_val not in record.getMessage()

    def test_no_scrub_when_no_log_false(self, state_logger, caplog):
        """``no_log`` not set -> records are untouched."""
        low = {}
        pillar_val = "not-secret-here"
        with caplog.at_level(logging.DEBUG, logger="salt.states.test_no_log_widened"):
            with _no_log_scope(low):
                state_logger.debug("value is %s", pillar_val)

        joined = " ".join(r.getMessage() for r in caplog.records)
        assert pillar_val in joined

    def test_other_loggers_not_scrubbed(self, caplog):
        """
        The scrub is scoped to ``salt.states.*`` loggers.  A log
        emitted by an unrelated logger (e.g. ``my.app``) should pass
        through even when a state with ``no_log: True`` is running.
        """
        low = {"no_log": True}
        unrelated = logging.getLogger("my.app.unrelated")
        unrelated.setLevel(logging.DEBUG)
        with caplog.at_level(logging.DEBUG, logger="my.app.unrelated"):
            with _no_log_scope(low):
                unrelated.debug("plain value %s", "visible")

        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "visible" in joined

    def test_filter_removed_on_exit(self, state_logger, caplog):
        """
        After ``_no_log_scope`` exits, records from the same logger
        must flow normally (the filter was removed from handlers).
        """
        low = {"no_log": True}
        with caplog.at_level(logging.DEBUG, logger="salt.states.test_no_log_widened"):
            with _no_log_scope(low):
                state_logger.debug("inside secret")
            state_logger.debug("outside visible")

        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "outside visible" in joined
        assert "inside secret" not in joined


if __name__ == "__main__":
    pytest.main([__file__, "-xvs"])
