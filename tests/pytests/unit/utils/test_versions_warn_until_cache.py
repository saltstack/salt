"""
Tests for the ``warn_until()`` memoized resolvers.

The two cached helpers convert ``warn_until()``'s hashable arguments into
:class:`salt.version.SaltStackVersion` instances once per unique input,
sparing hot paths that fire the deprecation warning per event from
allocating a fresh ``SaltStackVersion`` (and, transitively, a
:class:`packaging.version.Version`) on every call. See :issue:`69921`.
"""

import warnings

import pytest

import salt.utils.versions
import salt.version


def test_resolve_target_version_returns_same_instance_for_same_hashable_input():
    """Repeated identical inputs return the cached SaltStackVersion object."""
    resolve = salt.utils.versions._resolve_target_version_hashable
    resolve.cache_clear()
    try:
        v1 = resolve(3009)
        v2 = resolve(3009)
        assert v1 is v2
        assert isinstance(v1, salt.version.SaltStackVersion)
    finally:
        resolve.cache_clear()


def test_resolve_target_version_returns_none_for_unhandled_type():
    """Non-hashable / non-supported inputs signal the miss with ``None``."""
    resolve = salt.utils.versions._resolve_target_version_hashable
    resolve.cache_clear()
    try:
        assert resolve(object()) is None
    finally:
        resolve.cache_clear()


@pytest.mark.parametrize(
    "value",
    [
        3009,
        (3009, 0),
        "Argon",
    ],
)
def test_resolve_target_version_handles_supported_hashable_types(value):
    """int, tuple, and string inputs all produce a SaltStackVersion."""
    resolve = salt.utils.versions._resolve_target_version_hashable
    resolve.cache_clear()
    try:
        v = resolve(value)
        assert isinstance(v, salt.version.SaltStackVersion)
    finally:
        resolve.cache_clear()


def test_resolve_target_version_raises_on_unknown_release_name():
    """An unknown release name still raises the original ``RuntimeError``."""
    resolve = salt.utils.versions._resolve_target_version_hashable
    resolve.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="Incorrect spelling"):
            resolve("NotARelease")
    finally:
        resolve.cache_clear()


def test_resolve_current_version_returns_same_instance():
    """The current-version cache returns one shared instance per version_info tuple."""
    resolve = salt.utils.versions._resolve_current_version
    resolve.cache_clear()
    try:
        v1 = resolve((3008, 2))
        v2 = resolve((3008, 2))
        assert v1 is v2
        assert isinstance(v1, salt.version.SaltStackVersion)
    finally:
        resolve.cache_clear()


def test_warn_until_makes_zero_saltstackversion_allocations_after_warmup():
    """After the cache is warm, warn_until() no longer constructs
    SaltStackVersion objects on repeated calls with the same target."""
    original_init = salt.version.SaltStackVersion.__init__
    call_count = {"n": 0}

    def counting_init(self, *args, **kwargs):
        call_count["n"] += 1
        return original_init(self, *args, **kwargs)

    salt.utils.versions._resolve_target_version_hashable.cache_clear()
    salt.utils.versions._resolve_current_version.cache_clear()

    try:
        salt.version.SaltStackVersion.__init__ = counting_init
        # Warmup — this call is allowed to allocate.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            salt.utils.versions.warn_until(3009, "warmup")

        call_count["n"] = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for _ in range(1000):
                salt.utils.versions.warn_until(3009, "test")
        assert call_count["n"] == 0
    finally:
        salt.version.SaltStackVersion.__init__ = original_init
        salt.utils.versions._resolve_target_version_hashable.cache_clear()
        salt.utils.versions._resolve_current_version.cache_clear()


def test_warn_until_still_accepts_saltstackversion_target():
    """Passing a fully-constructed :class:`SaltStackVersion` bypasses the
    cache (as before) and still resolves correctly."""
    # A well-in-the-future major release so warn_until doesn't fire the
    # "past release" branch.
    future_version = salt.version.SaltStackVersion(
        salt.version.__version_info__[0] + 100
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Should not raise; the fall-through path handles this input inline.
        salt.utils.versions.warn_until(future_version, "future")


def test_warn_until_accepts_saltversion_target():
    """Passing a :class:`salt.version.SaltVersion` (a namedtuple that is
    unhashable due to a custom ``__eq__``) must be routed away from the
    ``lru_cache`` fast path — otherwise ``hash(version)`` blows up with
    ``TypeError: unhashable type: 'SaltVersion'`` before the function
    body even runs. Regression test for the CI failure on the initial
    landing of the memoize change."""
    # POTASSIUM is well in the future relative to 3008.x so warn_until
    # won't fire the "past release" branch when _version_info_ is set to
    # the current running version.
    future_saltversion = salt.version.SaltVersionsInfo.POTASSIUM
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Should not raise TypeError; the SaltVersion branch handles it.
        salt.utils.versions.warn_until(future_saltversion, "future")
