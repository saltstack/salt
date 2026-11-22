"""
Tests the HardCrashMixin.
"""

import pytest

import salt.defaults.exitcodes
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


@pytest.mark.parametrize("value", [None, "False", "false", "FALSE"])
def test_hard_crash_is_off(monkeypatch, value):
    assert _hard_crash(monkeypatch, value) is False


@pytest.mark.parametrize("value", ["True", "true", "TRUE"])
def test_hard_crash_is_on(monkeypatch, value):
    assert _hard_crash(monkeypatch, value) is True


@pytest.mark.parametrize(
    "value", ["", "1", "0", "yes", "no", "on", "off", "2", "truee", " True"]
)
def test_hard_crash_rejects_any_other_value(monkeypatch, capsys, value):
    with pytest.raises(SystemExit) as exc:
        _hard_crash(monkeypatch, value)
    assert exc.value.code == salt.defaults.exitcodes.EX_USAGE
    assert f"SALT_HARD_CRASH must be True or False, not '{value}'" in (
        capsys.readouterr().err
    )


def test_hard_crash_option_turns_it_on(monkeypatch):
    monkeypatch.delenv("SALT_HARD_CRASH", raising=False)
    parser = MockHardCrashParser()
    values = parser.get_default_values()
    parser._process_args([], ["--hard-crash"], values)
    assert values.hard_crash is True
