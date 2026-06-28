"""
Patch the salt onedir Python's ``Lib/ssl.py`` in place to apply
cpython#104135's iterate-and-skip variant of
``ssl.SSLContext._load_windows_store_certs``.

Usage: ``python windows-ssl-104135-patch.py <path-to-ssl.py>``

Background
----------

The build-deps-ci Windows job extracts the salt onedir, then runs
``nox --install-only -e ci-test-onedir`` and ``nox -e pre-archive-cleanup``.
Both sessions target the onedir's relenv-bundled Python (3.10.20 on 3006.x)
and create virtualenvs from it. The ``ci-test-onedir`` session uses
``--system-site-packages``; ``pre-archive-cleanup`` does not. Either way,
both venvs share the onedir's ``Lib/ssl.py`` because virtualenv leaves the
base Python's stdlib on ``sys.path``.

Python 3.10's stdlib ``ssl._load_windows_store_certs`` concatenates every
cert from the Windows root store and feeds them to
``load_verify_locations(cadata=...)`` as one blob. OpenSSL 3.5.x (shipped by
relenv >= 0.22.13) rejects the whole blob on a single ASN.1-malformed cert,
so pip's TLS to pypi.org dies with ``[ASN1: NOT_ENOUGH_DATA]`` before any
deps land. See cpython#104135.

Appending the patch to ``Lib/ssl.py`` means every Python invocation using
the onedir picks up the fix - the ``ci-test-onedir`` venv, the
``pre-archive-cleanup`` venv, the raw onedir python itself, anything.

A ``sitecustomize.py`` would only reach the venv that turns on
``--system-site-packages``; a ``Lib/ssl.py`` append covers both.

Self-disables on Python 3.12+ (whose stdlib already has the upstream
iterate-and-skip fix; 3.10 and 3.11 never received the backport).

Durable cleanup
~~~~~~~~~~~~~~~

The right home for this patch is relenv's cpython build step - patching
``Lib/ssl.py`` once during the onedir build means every consumer
(production salt installs, plus our CI) gets the fix without any
salt-side workarounds. Once a relenv release carrying that patch lands
in this branch's onedir, drop this file together with the trio it pairs
with:

  - ``salt/__init__.py`` ``_load_windows_store_certs`` monkey-patch
  - ``salt/ext/tornado/netutil.py`` Windows ``certifi.where()`` pin
  - the ``Patch cpython#104135 in onedir Lib/ssl.py`` workflow steps in
    ``.github/workflows/{build-deps-ci,test,test-packages}-action.yml``

Until then, also drop the lot on any branch whose onedir Python is >=
3.12.
"""

import sys

MARKER = "# >>> cpython#104135 patch (windows-ssl-104135-patch.py) <<<"

PATCH_BODY = f"""

{MARKER}
# Replace the pre-fix _load_windows_store_certs with the iterate-and-skip
# variant cpython merged for the 3.12 branch. See cpython#104135.
# Self-disable on Python 3.12+ (where Lib/ssl.py already has the upstream
# fix; 3.10 and 3.11 never received the backport) and on non-Windows.
import sys as _patch_sys

if _patch_sys.platform == "win32" and _patch_sys.version_info < (3, 12):

    def _salt_safe_load_windows_store_certs(
        self, storename, purpose, _SSLError=SSLError
    ):
        try:
            from _ssl import enum_certificates
        except ImportError:
            return
        try:
            for cert, encoding, trust in enum_certificates(storename):
                if encoding != "x509_asn":
                    continue
                if trust is True or purpose.oid in trust:
                    try:
                        self.load_verify_locations(cadata=cert)
                    except _SSLError:
                        pass
        except PermissionError:
            pass

    SSLContext._load_windows_store_certs = _salt_safe_load_windows_store_certs
"""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            f"usage: {argv[0]} <path-to-ssl.py>",
            file=sys.stderr,
        )
        return 2
    path = argv[1]
    with open(path, encoding="utf-8") as fh:
        contents = fh.read()
    if MARKER in contents:
        print(f"{path}: already patched, leaving alone")
        return 0
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(PATCH_BODY)
    print(f"{path}: appended cpython#104135 work-around")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
