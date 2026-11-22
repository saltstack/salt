"""
Tests the HardCrashMixin.
"""

import pytest

import salt.utils.parsers


class MockHardCrashParser(
    salt.utils.parsers.OptionParser,
    salt.utils.parsers.HardCrashMixin,
    metaclass=salt.utils.parsers.OptionParserMeta,
):
    pass


def _hard_crash(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("SALT_HARD_CRASH", raising=False)
    else:
        monkeypatch.setenv("SALT_HARD_CRASH", value)
    return MockHardCrashParser().get_default_values().hard_crash


@pytest.mark.parametrize("value", [None, ""])
def test_hard_crash_is_off_when_the_variable_is_not_set_or_empty(monkeypatch, value):
    assert not _hard_crash(monkeypatch, value)


@pytest.mark.parametrize("value", ["1", "0", "True", "true", "False", "false", "no"])
def test_hard_crash_is_on_for_any_other_value(monkeypatch, value):
    """
    Any value that is not empty turns the option on, also "0" and "false".
    That is how the variable has always worked.
    """
    assert _hard_crash(monkeypatch, value)


def test_hard_crash_option_turns_it_on(monkeypatch):
    monkeypatch.delenv("SALT_HARD_CRASH", raising=False)
    parser = MockHardCrashParser()
    values = parser.get_default_values()
    parser._process_args([], ["--hard-crash"], values)
    assert values.hard_crash is True
