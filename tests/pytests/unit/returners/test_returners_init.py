"""
Unit tests for salt.returners package helpers (``get_returner_options`` /
``_options_browser``).

Regression coverage for:

- https://github.com/saltstack/salt/issues/63980 — configured falsy values
  (``0``, ``0.0``, ``False``, ``[]``) must be yielded by
  ``_options_browser`` rather than being replaced by the supplied
  defaults.
- Plain-dict fallback (``__salt__["config.option"]`` undefined,
  ``cfg = __opts__``): ``_fetch_option`` returns ``None`` for a missing
  attribute. That ``None`` must fall through to the ``defaults`` branch
  rather than being yielded verbatim. Same class of bug as #69654 on
  3007.x/3008.x, which #69669 fixed there.
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


def test_options_browser_falls_back_to_default_when_fetch_returns_none():
    """
    Plain-dict fallback path: when ``__salt__["config.option"]`` is not
    available, ``cfg`` is the plain ``__opts__`` dict and
    ``_fetch_option`` returns ``None`` for a missing attribute (see
    ``salt/returners/__init__.py::_fetch_option``). That ``None`` must
    fall through to the ``defaults`` branch instead of being yielded
    verbatim.
    """
    defaults = {"my_option": 42}
    options = {"my_option": "my_option"}

    with patch.object(salt.returners, "_fetch_option", return_value=None):
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


def test_options_browser_plain_dict_cfg_falls_back_to_defaults():
    """
    End-to-end plain-dict-``cfg`` regression test (no ``_fetch_option``
    monkey-patching). Mirrors the ``saltext-prometheus`` failure mode
    from #69654: a returner passing ``__opts__`` as ``cfg`` with a rich
    ``defaults`` dict should receive the defaults for every unset
    attribute, not a dict full of ``None`` values.
    """
    cfg = {}  # __opts__ with no returner options configured
    defaults = {
        "exe": None,
        "filename": "/tmp/salt.prom",
        "uid": -1,
        "gid": -1,
        "mode": None,
        "match_exe": False,
        "proc_name": "salt-minion",
    }
    options = {name: name for name in defaults}

    result = dict(
        salt.returners._options_browser(
            cfg=cfg,
            ret_config=None,
            defaults=defaults,
            virtualname="custom_returner",
            options=options,
        )
    )

    assert result == defaults


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
