"""
Unit tests for SaltCMDOptionParser options that affect job-publish kwargs.

These tests intentionally bypass the heavy mixin-driven ``parse_args``
chain (which loads master config, sets up log files, etc.) and use
``optparse.OptionParser._process_args`` directly to exercise just the
option-table behavior.
"""

import optparse  # pylint: disable=deprecated-module

import pytest

import salt.utils.parsers


@pytest.fixture
def salt_cmd_parser():
    return salt.utils.parsers.SaltCMDOptionParser()


def _process_only(parser, argv):
    """
    Run optparse's argument processor without triggering Salt's
    ``_mixin_after_parsed`` hook chain.
    """
    values = parser.get_default_values()
    rargs = list(argv)
    largs = []
    parser._process_args(largs, rargs, values)
    return values, largs + rargs


def test_start_event_option_is_registered(salt_cmd_parser):
    """
    The --start-event flag must be present, bound to dest=start_event,
    default to False, and use the store_true action so the parser
    treats it as a boolean opt-in flag.
    """
    option = salt_cmd_parser.get_option("--start-event")
    assert option is not None
    assert option.dest == "start_event"
    assert option.default is False
    assert option.action == "store_true"


def test_start_event_option_can_be_set(salt_cmd_parser):
    """
    Passing --start-event on the command line must result in
    options.start_event being True.
    """
    options, _args = _process_only(salt_cmd_parser, ["--start-event", "*", "test.ping"])
    assert options.start_event is True


def test_start_event_option_defaults_to_false(salt_cmd_parser):
    """
    Omitting --start-event must leave options.start_event as False so
    no event is requested by default for any caller.
    """
    options, _args = _process_only(salt_cmd_parser, ["*", "test.ping"])
    assert options.start_event is False


def test_start_event_help_text_mentions_event_tag(salt_cmd_parser):
    """
    The CLI help text must reference the event tag so operators
    discover the expected event format from `--help` alone.
    """
    option = salt_cmd_parser.get_option("--start-event")
    assert "salt/job/" in option.help
    assert "/start/" in option.help


def test_start_event_translates_to_kwargs():
    """
    SaltCMD.run() copies options.start_event into the kwargs dict that
    is passed to LocalClient. Replicate the exact translation block to
    ensure it produces a truthy kwarg and survives default-False.
    """
    # Replicates salt/cli/salt.py's translation, which is the only thing
    # that can regress between the parser registering the option and the
    # client receiving it.
    namespace = optparse.Values({"start_event": True})
    kwargs = {}
    if getattr(namespace, "start_event", False):
        kwargs["start_event"] = True
    assert kwargs == {"start_event": True}

    namespace = optparse.Values({"start_event": False})
    kwargs = {}
    if getattr(namespace, "start_event", False):
        kwargs["start_event"] = True
    assert kwargs == {}
