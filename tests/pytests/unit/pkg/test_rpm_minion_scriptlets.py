"""
Regression tests for the RPM ``%pre minion`` / ``%posttrans minion``
scriptlets.

The ``%pre minion`` scriptlet unconditionally stops the running minion
service on upgrade so the ownership-restoration chowns in ``%post`` /
``%posttrans`` don't race a live process. The historical
``%post`` / ``%posttrans`` scriptlets only called
``systemctl try-restart salt-minion.service``, which by design is a
no-op when the unit is inactive. The combination silently broke RPM
upgrades on every EL host: the minion was stopped by ``%pre`` and never
started again, leaving operators with no automatic recovery short of
logging into each host. See https://github.com/saltstack/salt/issues/69605.

This file is a *static audit* of ``pkg/rpm/salt.spec``. It runs in
ordinary unit-test CI - no rpmbuild, no systemd, no fixtures - so the
guard kicks in on every PR rather than only in the packaging matrix.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_FILE = REPO_ROOT / "pkg" / "rpm" / "salt.spec"


def _extract_scriptlet(spec_text, directive):
    """
    Return the body of an RPM scriptlet ``directive`` (e.g. ``%pre minion``)
    up to the next scriptlet directive or end of file.
    """
    # Match the directive at the start of a line, then capture until the
    # next directive that begins at column 0.
    pattern = re.compile(
        rf"^{re.escape(directive)}\s*\n(.*?)(?=^%(?:pre|post|posttrans|preun|postun|files|changelog|description|package)\b|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(spec_text)
    assert match is not None, f"{directive!r} scriptlet not found in salt.spec"
    return match.group(1)


@pytest.fixture(scope="module")
def spec_text():
    assert SPEC_FILE.is_file(), f"spec file missing: {SPEC_FILE}"
    return SPEC_FILE.read_text(encoding="utf-8")


def test_pre_minion_records_was_active_before_stop(spec_text):
    """
    ``%pre minion`` must record the unit's pre-upgrade active state
    before invoking ``systemctl stop``. Otherwise ``%posttrans`` has no
    way to know whether the service should be brought back up. See
    https://github.com/saltstack/salt/issues/69605.
    """
    body = _extract_scriptlet(spec_text, "%pre minion")
    stop_idx = body.find("systemctl stop salt-minion.service")
    assert stop_idx != -1, (
        "%pre minion no longer stops salt-minion.service on upgrade. "
        "If this was deliberate, drop the matching marker handling in "
        "%posttrans minion too."
    )
    is_active_idx = body.find("systemctl is-active")
    assert is_active_idx != -1, (
        "%pre minion stops salt-minion.service but never records whether "
        "the unit was previously active. %posttrans minion cannot bring "
        "it back without that marker. See issue #69605."
    )
    assert is_active_idx < stop_idx, (
        "%pre minion records the active-state marker *after* the "
        "systemctl stop. The check must happen before the stop or it "
        "will always observe ``inactive``. See issue #69605."
    )


def test_posttrans_minion_starts_when_was_active(spec_text):
    """
    ``%posttrans minion`` must use ``systemctl start`` (not just
    ``try-restart``) when the ``%pre`` scriptlet recorded that the unit
    was previously active. ``try-restart`` is a documented no-op for an
    inactive unit, so on its own it cannot recover from the deliberate
    stop in ``%pre``. See https://github.com/saltstack/salt/issues/69605.
    """
    body = _extract_scriptlet(spec_text, "%posttrans minion")
    # The scriptlet must reference the marker file dropped by %pre.
    assert "salt-minion-upgrade-was-active" in body, (
        "%posttrans minion does not consult the pre-upgrade-active "
        "marker; an upgrade that finds the minion running will leave "
        "it stopped. See issue #69605."
    )
    # And it must run ``systemctl start`` (not just ``try-restart``) in
    # response. The cheapest robust check is to ensure both tokens
    # appear in the scriptlet text.
    assert re.search(r"systemctl\s+start\s+salt-minion\.service", body), (
        "%posttrans minion does not call ``systemctl start "
        "salt-minion.service``; ``try-restart`` is a no-op when the "
        "unit is inactive and cannot recover from %pre's stop. See "
        "issue #69605."
    )
