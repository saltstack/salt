"""
Unit tests for salt.returners package helpers (``get_returner_options`` /
``_options_browser``).

Regression coverage for https://github.com/saltstack/salt/issues/63980:
configured falsy values (``0``, ``0.0``, ``False``, ``[]``) must be
yielded by ``_options_browser`` rather than being replaced by the
supplied defaults.
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
    A falsy-but-set configuration value must be returned as-is instead of
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
