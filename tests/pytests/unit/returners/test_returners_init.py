"""
Unit tests for salt.returners package helpers (``get_returner_options`` /
``_options_browser``).
"""

import pytest

import salt.returners
from tests.support.mock import patch


@pytest.mark.parametrize(
    "configured_value",
    [0, 0.0, False, []],
    ids=["int-zero", "float-zero", "bool-false", "empty-list"],
)
def test_options_browser_yields_falsy_configured_value(configured_value):
    """
    Regression coverage for https://github.com/saltstack/salt/issues/63980:
    a falsy-but-set configuration value must be returned as-is instead of
    being masked by the returner's default value.
    """
    defaults = {"my_option": 42}
    options = {"my_option": "my_option"}

    with patch.object(salt.returners, "_fetch_option", return_value=configured_value):
        result = dict(
            salt.returners._options_browser(
                cfg=None,
                ret_config=None,
                defaults=defaults,
                virtualname="custom_returner",
                options=options,
            )
        )

    assert result == {"my_option": configured_value}


def test_options_browser_falls_back_to_default_when_unset():
    """
    When ``_fetch_option`` returns the empty-string sentinel (i.e. the
    option is not configured), the default value should be yielded.
    """
    defaults = {"my_option": 42}
    options = {"my_option": "my_option"}

    with patch.object(salt.returners, "_fetch_option", return_value=""):
        result = dict(
            salt.returners._options_browser(
                cfg=None,
                ret_config=None,
                defaults=defaults,
                virtualname="custom_returner",
                options=options,
            )
        )

    assert result == {"my_option": 42}


def test_options_browser_yields_configured_truthy_value():
    """
    A configured, truthy value should be yielded unchanged.
    """
    defaults = {"my_option": 42}
    options = {"my_option": "my_option"}

    with patch.object(salt.returners, "_fetch_option", return_value="hello"):
        result = dict(
            salt.returners._options_browser(
                cfg=None,
                ret_config=None,
                defaults=defaults,
                virtualname="custom_returner",
                options=options,
            )
        )

    assert result == {"my_option": "hello"}


def test_options_browser_falls_back_to_default_when_none():
    """
    Regression coverage for https://github.com/saltstack/salt/issues/69654:
    when ``_fetch_option`` returns ``None`` (for example because the config
    source is a plain ``__opts__`` dict without a value for the attribute),
    the default value must be yielded instead of a bare ``None``.
    """
    defaults = {
        "filename": "/tmp/prometheus.prom",
        "uid": -1,
        "gid": -1,
        "match_exe": False,
        "proc_name": "salt-minion",
    }
    options = {k: k for k in defaults}

    with patch.object(salt.returners, "_fetch_option", return_value=None):
        result = dict(
            salt.returners._options_browser(
                cfg=None,
                ret_config=None,
                defaults=defaults,
                virtualname="prometheus_textfile",
                options=options,
            )
        )

    assert result == defaults


def test_get_returner_options_defaults_with_plain_opts_dict():
    """
    Regression coverage for https://github.com/saltstack/salt/issues/69654:
    when ``get_returner_options`` is called with ``__opts__`` that does not
    contain the returner's attributes (and ``__salt__`` has no
    ``config.option``), each unset attribute should fall through to its
    ``defaults`` value rather than being yielded as ``None``.
    """
    opts = {"cachedir": "/tmp"}
    defaults = {
        "exe": None,
        "filename": "/tmp/prometheus.prom",
        "uid": -1,
        "gid": -1,
        "mode": None,
        "match_exe": False,
        "proc_name": "salt-minion",
        "add_state_name": False,
    }
    attrs = {k: k for k in defaults}

    result = salt.returners.get_returner_options(
        "prometheus_textfile",
        ret=None,
        attrs=attrs,
        __salt__={},
        __opts__=opts,
        defaults=defaults,
    )

    assert result == defaults
