"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.logrotate
"""

import textwrap

import pytest

import salt.modules.logrotate as logrotate
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def PARSE_CONF():
    return {
        "include files": {"rsyslog": ["/var/log/syslog"]},
        "rotate": 1,
        "/var/log/wtmp": {"rotate": 1},
    }


@pytest.fixture
def configure_loader_modules():
    return {logrotate: {}}


# 'show_conf' function tests: 1


def test_show_conf():
    """
    Test if it show parsed configuration
    """
    with patch("salt.modules.logrotate._parse_conf", MagicMock(return_value=True)):
        assert logrotate.show_conf()


# 'set_' function tests: 4


def test_set(PARSE_CONF):
    """
    Test if it set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ), patch.dict(logrotate.__salt__, {"file.replace": MagicMock(return_value=True)}):
        assert logrotate.set_("rotate", "2")


def test_set_failed(PARSE_CONF):
    """
    Test if it fails to set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        kwargs = {"key": "/var/log/wtmp", "value": 2}
        pytest.raises(SaltInvocationError, logrotate.set_, **kwargs)


def test_set_setting(PARSE_CONF):
    """
    Test if it set a new value for a specific configuration line
    """
    with patch.dict(
        logrotate.__salt__, {"file.replace": MagicMock(return_value=True)}
    ), patch("salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)):
        assert logrotate.set_("/var/log/wtmp", "rotate", "2")


def test_set_setting_failed(PARSE_CONF):
    """
    Test if it fails to set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        kwargs = {"key": "rotate", "value": "/var/log/wtmp", "setting": "2"}
        pytest.raises(SaltInvocationError, logrotate.set_, **kwargs)


def test_parse_conf_preserves_script_blocks(tmp_path):
    """
    Regression test for #68293.

    ``_parse_conf`` must treat the body of ``prerotate``/``postrotate``/
    ``firstaction``/``lastaction``/``preremove`` blocks as opaque script
    content terminated by ``endscript``. Previously every line inside the
    block was treated as a key/value setting, so the two ``endscript`` lines
    collapsed into a single dict key, the embedded shell commands became
    bogus setting keys, and rewriting the stanza dropped the second
    ``endscript`` — breaking the rendered logrotate configuration.
    """
    conf = textwrap.dedent(
        """\
        /parsec/log/system/events {
            rotate 10
            size 18M
            missingok
            notifempty
            compress
            delaycompress
            sharedscripts
            prerotate
            chattr -a /parsec/log/system/events > /dev/null
            endscript
            postrotate
            system-protect-event-log > /dev/null
            invoke-rc.d syslog-ng reload > /dev/null
            endscript
        }
        """
    )
    conf_file = tmp_path / "logrotate.conf"
    conf_file.write_text(conf)

    parsed = logrotate._parse_conf(str(conf_file))
    stanza = parsed["/parsec/log/system/events"]

    # The script bodies are preserved verbatim, keyed by the script directive.
    assert stanza["prerotate"] == [
        "chattr -a /parsec/log/system/events > /dev/null",
    ]
    assert stanza["postrotate"] == [
        "system-protect-event-log > /dev/null",
        "invoke-rc.d syslog-ng reload > /dev/null",
    ]

    # The shell commands inside the script blocks must not leak into the
    # stanza as bogus setting keys.
    for leaked in ("chattr", "system-protect-event-log", "invoke-rc.d"):
        assert leaked not in stanza, (
            f"{leaked!r} was parsed as a setting key — script block was not"
            " kept opaque"
        )

    # ``endscript`` is a block terminator, not a setting in its own right.
    assert "endscript" not in stanza

    # ``_dict_to_stanza`` must round-trip both script blocks with their own
    # ``endscript`` terminator each.
    rendered = logrotate._dict_to_stanza("/parsec/log/system/events", stanza)
    assert rendered.count("endscript") == 2, rendered
    assert "prerotate\n" in rendered, rendered
    assert "postrotate\n" in rendered, rendered
    assert "chattr -a /parsec/log/system/events > /dev/null" in rendered
    assert "invoke-rc.d syslog-ng reload > /dev/null" in rendered


def test_get(PARSE_CONF):
    """
    Test if get a value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        # A single key returns the right value
        assert logrotate.get("rotate") == 1

        # A single key returns the wrong value
        assert logrotate.get("rotate") != 2

        # A single key returns the right stanza value
        assert logrotate.get("/var/log/wtmp", "rotate") == 1

        # A single key returns the wrong stanza value
        assert logrotate.get("/var/log/wtmp", "rotate") != 2

        # Ensure we're logging the message as debug not warn
        with patch.object(logrotate, "_LOG") as log_mock:
            res = logrotate.get("/var/log/utmp", "rotate")
            assert log_mock.debug.called
            assert not log_mock.warn.called
