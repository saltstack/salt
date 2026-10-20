"""
Static checks on the Debian package maintainer scripts.

Regression coverage for issue #68460: when upgrading the Debian
``salt-minion`` package from a non-onedir release (e.g. ``3006.0+ds-1+240.1``
shipped by Debian), ``/opt/saltstack/salt/bin/python3`` does not exist yet
because the new package has not been unpacked. The ``preinst`` script runs
with ``set -e``, so any reference to that interpreter aborts the install with
``subprocess returned error exit status 127`` and dpkg refuses to upgrade.

The ``preinst`` script must therefore not depend on the onedir Python binary.
"""

import pathlib

from tests.conftest import CODE_DIR

DEBIAN_PKG_DIR = pathlib.Path(CODE_DIR) / "pkg" / "debian"


def test_salt_minion_preinst_does_not_invoke_onedir_python():
    """
    ``salt-minion.preinst`` must not invoke ``/opt/saltstack/salt/bin/python3``.

    The binary is shipped *by* the new package and is therefore missing during
    a ``preinst upgrade`` from a non-onedir version. Calling it aborts the
    upgrade under ``set -e`` (see issue #68460).
    """
    preinst = DEBIAN_PKG_DIR / "salt-minion.preinst"
    contents = preinst.read_text()
    assert "/opt/saltstack/salt/bin/python3" not in contents, (
        "salt-minion.preinst must not invoke /opt/saltstack/salt/bin/python3 "
        "because that interpreter is not available when upgrading from a "
        "non-onedir Salt package (issue #68460)."
    )
