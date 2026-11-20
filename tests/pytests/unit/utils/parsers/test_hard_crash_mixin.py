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


@pytest.mark.parametrize("value", [None, "", "0", "false", "False", "no", "off"])
def test_hard_crash_is_off_when_the_variable_says_no(monkeypatch, value):
    assert not _hard_crash(monkeypatch, value)


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on"])
def test_hard_crash_is_on_when_the_variable_says_yes(monkeypatch, value):
    assert _hard_crash(monkeypatch, value)


def test_hard_crash_option_turns_it_on(monkeypatch):
    monkeypatch.delenv("SALT_HARD_CRASH", raising=False)
    parser = MockHardCrashParser()
    values = parser.get_default_values()
    parser._process_args([], ["--hard-crash"], values)
    assert values.hard_crash is True
