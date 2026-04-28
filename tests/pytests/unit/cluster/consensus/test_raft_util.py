"""Tests for ``salt.cluster.consensus.raft.util`` helpers."""

import pytest

from salt.cluster.consensus.raft import (
    CounterStateMachine,
    gettimeout,
    load_class,
    log_generator,
)


def test_log_generator_default_alphanumeric():
    s = log_generator(12)
    assert len(s) == 12
    assert s.isalnum()


def test_log_generator_custom_alphabet():
    s = log_generator(20, chars="ab")
    assert len(s) == 20
    assert set(s) <= {"a", "b"}


def test_gettimeout_milliseconds_are_seconds():
    for _ in range(40):
        t = gettimeout(150, 300)
        assert 0.15 <= t <= 0.30


def test_load_class_counter_state_machine():
    cls = load_class("salt.cluster.consensus.raft.log.CounterStateMachine")
    assert cls is CounterStateMachine
    assert cls() is not None


def test_load_class_via_package_export():
    cls = load_class("salt.cluster.consensus.raft.CounterStateMachine")
    assert cls is CounterStateMachine


def test_load_class_invalid_module():
    with pytest.raises(ImportError, match="Failed to load class"):
        load_class("definitely_not_a_real_module_zzz.SomeClass")


def test_load_class_invalid_attribute():
    with pytest.raises(ImportError, match="Failed to load class"):
        load_class("salt.cluster.consensus.raft.log.NotARealClassName")
