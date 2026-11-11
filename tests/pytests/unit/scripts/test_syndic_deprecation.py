"""
Pin the deprecation signal on ``salt.scripts.salt_syndic``.

The syndic daemon has been superseded by master topology
(``topology_enabled: True`` with per-peer links). ``salt_syndic`` must
emit a ``DeprecationWarning`` at entry so operators running the
``salt-syndic`` CLI see an audible migration cue, while the daemon
continues to start normally during the deprecation window.

This test is a regression anchor for that behavior. It should fail if
the warning is removed, downgraded (e.g. to ``PendingDeprecationWarning``
or a plain log line), or has its user-facing text stripped of the
"topology" migration pointer.
"""

import warnings

import salt.scripts
from tests.support.mock import MagicMock, patch


def test_salt_syndic_emits_deprecation_warning():
    """
    Calling ``salt_syndic`` emits a ``DeprecationWarning`` whose message
    names the daemon and points operators at master topology as the
    migration target. The underlying ``Syndic`` daemon is mocked so the
    test exercises only the entrypoint, not a live syndic start.
    """
    fake_syndic = MagicMock()
    with patch("salt.cli.daemons.Syndic", return_value=fake_syndic), patch(
        "salt.utils.process.notify_systemd"
    ), patch.object(salt.scripts, "_pin_multiprocessing_fork"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            salt.scripts.salt_syndic()

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations, (
        "salt_syndic() must emit a DeprecationWarning; got categories="
        f"{[w.category.__name__ for w in caught]!r}"
    )

    # Exactly one deprecation banner from salt_syndic itself. If a future
    # change surfaces additional deprecations here, update the message
    # assertion below to target the right record rather than relaxing it.
    syndic_warnings = [
        w
        for w in deprecations
        if "salt-syndic" in str(w.message).lower()
        or "syndic daemon" in str(w.message).lower()
    ]
    assert syndic_warnings, (
        "DeprecationWarning must mention the syndic daemon by name; got: "
        f"{[str(w.message) for w in deprecations]!r}"
    )

    msg = str(syndic_warnings[0].message)
    # Migration pointer: operators need to know *what* to move to.
    assert (
        "topology" in msg.lower()
    ), f"DeprecationWarning must point operators at master topology; got: {msg!r}"

    # The warning must fire before (or at least alongside) daemon start,
    # not after a successful run. Confirm Syndic().start() is still invoked
    # so the deprecation path does not short-circuit normal operation.
    fake_syndic.start.assert_called_once()


def test_salt_syndic_deprecation_category_is_not_pending():
    """
    ``PendingDeprecationWarning`` is silent by default under CPython and
    would not reach operators running ``salt-syndic`` interactively. The
    entrypoint must use the louder ``DeprecationWarning`` so the banner
    is visible without a custom warnings filter.
    """
    fake_syndic = MagicMock()
    with patch("salt.cli.daemons.Syndic", return_value=fake_syndic), patch(
        "salt.utils.process.notify_systemd"
    ), patch.object(salt.scripts, "_pin_multiprocessing_fork"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            salt.scripts.salt_syndic()

    categories = {w.category for w in caught}
    assert (
        DeprecationWarning in categories
    ), f"Expected DeprecationWarning in {[c.__name__ for c in categories]!r}"
    # Guard against silently downgrading to PendingDeprecationWarning only;
    # PendingDeprecationWarning is filtered out by CPython's default filters
    # and would not be surfaced to operators running the CLI interactively.
    syndic_messages = [w for w in caught if "syndic" in str(w.message).lower()]
    syndic_categories = {w.category for w in syndic_messages}
    assert DeprecationWarning in syndic_categories, (
        "The syndic-specific warning must be a DeprecationWarning, got: "
        f"{[c.__name__ for c in syndic_categories]!r}"
    )
    assert syndic_categories != {PendingDeprecationWarning}, (
        "salt_syndic must not downgrade the signal to PendingDeprecationWarning "
        "(CPython's default filters hide it from interactive operators)."
    )
