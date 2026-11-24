"""
Unit tests for :mod:`salt._logging.filters.pillar`.

Covers the content-match redaction behaviour, the min-length floor,
the disabled fast path, snapshot refresh on pillar reassignment, and
the handler-level install helper.
"""

import logging

import pytest

from salt._logging.filters.pillar import (
    MIN_VALUE_LENGTH,
    REDACT_PLACEHOLDER,
    PillarRedactingFilter,
    install_on_handler,
)


def _make_record(msg, args=None, name="salt.states.pkg"):
    # LogRecord unwraps a single-dict tuple to a plain dict; bypass
    # that by assigning args after construction so tests can round-trip
    # any shape.
    record = logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )
    record.args = args
    return record


class TestDisabledFastPath:
    def test_passthrough_when_disabled(self):
        flt = PillarRedactingFilter(
            {
                "pillar_mask_output": False,
                "pillar": {"db": {"root_password": "hunter2secret"}},
            }
        )
        record = _make_record("pillar value is hunter2secret", args=("hunter2secret",))
        assert flt.filter(record) is True
        assert record.msg == "pillar value is hunter2secret"
        assert record.args == ("hunter2secret",)

    def test_passthrough_when_opts_missing(self):
        flt = PillarRedactingFilter()
        record = _make_record("anything goes")
        assert flt.filter(record) is True
        assert record.msg == "anything goes"


class TestContentMatch:
    def _filter(self, pillar):
        return PillarRedactingFilter({"pillar_mask_output": True, "pillar": pillar})

    def test_redacts_string_leaf_in_msg(self):
        flt = self._filter({"db": {"root_password": "hunter2secret"}})
        record = _make_record("the password is hunter2secret here")
        flt.filter(record)
        assert record.msg == f"the password is {REDACT_PLACEHOLDER} here"

    def test_redacts_string_leaf_in_args(self):
        flt = self._filter({"api": {"token": "s3cr3tt0k3n"}})
        record = _make_record("token %s", args=("s3cr3tt0k3n",))
        flt.filter(record)
        assert record.args == (REDACT_PLACEHOLDER,)

    def test_redacts_nested_dict_leaves(self):
        flt = self._filter(
            {"app": {"db": {"password": "topsecret"}, "token": "beartoken"}}
        )
        record = _make_record(
            "topsecret and beartoken appear", args=({"nested": "beartoken"},)
        )
        flt.filter(record)
        assert "topsecret" not in record.msg
        assert "beartoken" not in record.msg
        assert record.args[0]["nested"] == REDACT_PLACEHOLDER

    def test_redacts_list_leaves(self):
        flt = self._filter({"certs": ["cert_aaaaaa", "cert_bbbbbb"]})
        record = _make_record("certs: cert_aaaaaa and cert_bbbbbb")
        flt.filter(record)
        assert record.msg == f"certs: {REDACT_PLACEHOLDER} and {REDACT_PLACEHOLDER}"

    def test_redacts_bytes_leaf(self):
        flt = self._filter({"k": b"deadbeefbytes"})
        record = _make_record("value deadbeefbytes seen")
        flt.filter(record)
        assert record.msg == f"value {REDACT_PLACEHOLDER} seen"

    def test_redacts_int_leaf(self):
        flt = self._filter({"port": 48506})
        record = _make_record("listening on 48506")
        flt.filter(record)
        assert record.msg == f"listening on {REDACT_PLACEHOLDER}"

    def test_longest_first_handles_overlap(self):
        # If both "hunter2" and "hunter2extralong" are leaves, the
        # longer one must win so we don't leave "extralong" behind.
        flt = self._filter({"a": "hunter2", "b": "hunter2extralong"})
        record = _make_record("value hunter2extralong")
        flt.filter(record)
        assert record.msg == f"value {REDACT_PLACEHOLDER}"


class TestMinimumLengthFloor:
    def test_short_values_are_not_redacted(self):
        # Under MIN_VALUE_LENGTH chars: must NOT be redacted (would
        # collide too often with ordinary log text).
        pillar = {"env": "qa", "x": "ab"}
        flt = PillarRedactingFilter({"pillar_mask_output": True, "pillar": pillar})
        record = _make_record("env is qa and ab")
        flt.filter(record)
        assert record.msg == "env is qa and ab"

    def test_values_at_floor_are_redacted(self):
        assert MIN_VALUE_LENGTH == 4
        flt = PillarRedactingFilter(
            {"pillar_mask_output": True, "pillar": {"k": "abcd"}}
        )
        record = _make_record("value abcd here")
        flt.filter(record)
        assert record.msg == f"value {REDACT_PLACEHOLDER} here"

    def test_booleans_are_not_redacted(self):
        # "True"/"False" collisions would be absurd.
        flt = PillarRedactingFilter(
            {
                "pillar_mask_output": True,
                "pillar": {"enabled": True, "disabled": False},
            }
        )
        record = _make_record("enabled=True disabled=False")
        flt.filter(record)
        assert record.msg == "enabled=True disabled=False"


class TestRefreshOnPillarSwap:
    def test_rebinding_pillar_refreshes_snapshot(self):
        opts = {
            "pillar_mask_output": True,
            "pillar": {"k": "oldsecretvalue"},
        }
        flt = PillarRedactingFilter(opts)

        record = _make_record("oldsecretvalue appears")
        flt.filter(record)
        assert record.msg == f"{REDACT_PLACEHOLDER} appears"

        # Swap pillar (new dict identity) and verify the new value is
        # redacted while the old one is no longer in the regex.
        opts["pillar"] = {"k": "newsecretvalue"}
        record = _make_record("newsecretvalue appears")
        flt.filter(record)
        assert record.msg == f"{REDACT_PLACEHOLDER} appears"

        record = _make_record("oldsecretvalue appears")
        flt.filter(record)
        assert record.msg == "oldsecretvalue appears"

    def test_explicit_refresh_rebuilds_snapshot(self):
        opts = {
            "pillar_mask_output": True,
            "pillar": {"k": "originalval"},
        }
        flt = PillarRedactingFilter(opts)

        # Mutate the SAME dict in-place; id() won't change, so lazy
        # refresh won't fire -- but explicit refresh() should.
        opts["pillar"]["k"] = "mutatedvalue"
        flt.refresh()

        record = _make_record("mutatedvalue here")
        flt.filter(record)
        assert record.msg == f"{REDACT_PLACEHOLDER} here"


class TestBehaviorAlwaysReturnsTrue:
    def test_filter_bug_does_not_block_record(self, monkeypatch):
        """A bug inside the filter must never silence logging."""
        flt = PillarRedactingFilter(
            {"pillar_mask_output": True, "pillar": {"k": "normalval"}}
        )

        def boom(*args, **kwargs):
            raise RuntimeError("synthetic filter bug")

        monkeypatch.setattr(flt, "_scrub", boom)
        record = _make_record("normalval", args=({"a": "normalval"},))
        # Must not raise; must return True; record may be partially
        # scrubbed or unchanged.
        assert flt.filter(record) is True


class TestInstallOnHandler:
    def test_attaches_once(self):
        handler = logging.Handler()
        opts = {"pillar_mask_output": True, "pillar": {"k": "unique_val"}}

        f1 = install_on_handler(handler, opts)
        f2 = install_on_handler(handler, opts)

        assert f1 is f2
        assert sum(isinstance(f, PillarRedactingFilter) for f in handler.filters) == 1

    def test_second_install_refreshes_opts(self):
        handler = logging.Handler()
        opts_a = {"pillar_mask_output": True, "pillar": {"k": "aaaaaaaa"}}
        opts_b = {"pillar_mask_output": True, "pillar": {"k": "bbbbbbbb"}}

        f1 = install_on_handler(handler, opts_a)
        f2 = install_on_handler(handler, opts_b)
        assert f1 is f2

        record = _make_record("bbbbbbbb and aaaaaaaa")
        f1.filter(record)
        assert "bbbbbbbb" not in record.msg
        # Snapshot was rebound to opts_b, so aaaaaaaa is no longer in
        # the regex and must be left alone.
        assert "aaaaaaaa" in record.msg

    def test_none_handler_is_a_noop(self):
        assert install_on_handler(None, {"pillar_mask_output": True}) is None


@pytest.mark.parametrize("value", ["", None])
def test_empty_or_none_pillar(value):
    opts = {"pillar_mask_output": True, "pillar": value}
    flt = PillarRedactingFilter(opts)
    record = _make_record("nothing to redact here")
    assert flt.filter(record) is True
    assert record.msg == "nothing to redact here"
