import logging
import warnings

import pytest

import salt.utils._yaml_common as _yc
from tests.support.mock import patch

log = logging.getLogger(__name__)


def pytest_configure(config):
    config.addinivalue_line("markers", "show_yaml_compatibility_warnings")


@pytest.fixture(autouse=True)
def suppress_yaml_compatibility_warnings(request):
    """Silence the warnings produced by certain ``yaml_compatibility`` values.

    This is an autouse fixture, so warnings are always suppressed by default
    assuming this module is loaded.  To un-suppress the warnings, you can either
    redefine this fixture to be a no-op:

    .. code-block:: python

        @pytest.fixture
        def suppress_yaml_compatibility_warnings():
            pass

    or you can mark your tests with ``show_yaml_compatibility_warnings``:

    .. code-block:: python

        @pytest.mark.show_yaml_compatibility_warnings
        @pytest.mark.parametrize("yaml_compatibility", [3006], indirect=True)
        def test_yaml_compatibility_warning_3006(yaml_compatibility):
            with pytest.warns(FutureWarning):
                salt.utils.yaml.load("{}")

    """
    if "show_yaml_compatibility_warnings" in request.keywords:
        yield
        return
    log.debug("suppressing YAML compatibility warnings")
    with warnings.catch_warnings():
        # Don't suppress UnsupportedValueWarning in _yc.compat_ver() -- that
        # warning means that a test needs to be updated.
        for category in [FutureWarning, _yc.OverrideNotice]:
            warnings.filterwarnings("ignore", category=category, module=_yc.__name__)
        yield


@pytest.fixture
def clear_internal_compat_ver_state():
    """Reprocess ``yaml_compatibility`` next time ``compat_ver`` is called.

    This temporarily clears the internal state containing the processed
    ``yaml_compatibility`` version, forcing the next ``compat_ver`` call to
    reprocess the ``yaml_compatibility`` option.

    """
    # It would be nice if contextvars.copy_context() could be used as a context
    # manager, but alas we have to individually back up the context variables
    # and restore them later.  https://github.com/python/cpython/issues/99633
    opt_tok = _yc._compat_opt.set(None)
    ver_tok = _yc._compat_ver.set(None)
    yield
    _yc._compat_ver.reset(ver_tok)
    _yc._compat_opt.reset(opt_tok)


@pytest.fixture
def yaml_compatibility(
    request, suppress_yaml_compatibility_warnings, clear_internal_compat_ver_state
):
    """Temporarily override the ``yaml_compatibility`` option.

    To specify the desired ``yaml_compatibility`` value, use indirect
    parametrization:

    .. code-block:: python

        @pytest.mark.parametrize("yaml_compatibility", [3006], indirect=True)
        def test_foo(yaml_compatibility):
            assert yaml_compatibility == 3006
            want = salt.version.SaltStackVersion(3006)
            got = salt.utils._yaml_common.compat_ver()
            assert got == want

    If a parameter is not given, ``yaml_compatibility`` behaves as if the
    parameter was ``None``.

    """
    v = getattr(request, "param", None)
    log.debug(f"setting yaml_compatibility to {v!r}")
    _yc._init()  # Ensure _yc.__opts__ is initialized before patching it.
    with patch.dict(_yc.__opts__, {"yaml_compatibility": v}):
        yield v
    log.debug(f"restoring yaml_compatibility")
