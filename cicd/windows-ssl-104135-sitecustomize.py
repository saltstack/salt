"""
sitecustomize hook applied to the salt onedir Python during CI builds.

The build-deps-ci Windows job extracts the salt onedir, then runs
``nox --install-only -e ci-test-onedir``. ``noxfile.py``'s
``ci-test-onedir`` session targets the onedir's relenv-bundled Python -
on 3006.x that is Python 3.10.20 - and nox creates a virtualenv from it
with ``--system-site-packages``. pip then runs inside that venv and
fetches setuptools/pip/wheel from pypi.org over HTTPS *before* salt
itself has been installed.

Python 3.10's stdlib ``ssl._load_windows_store_certs`` concatenates
every cert from the Windows root store and feeds them to
``load_verify_locations(cadata=...)`` as one blob. Under the strict
ASN.1 parser shipped by OpenSSL 3.5.x (which relenv >= 0.22.13 bundles)
one malformed cert in the OS store aborts the whole load with
``[ASN1: NOT_ENOUGH_DATA]``, so pip fails to verify pypi.org's TLS
cert chain and the CI-Deps job dies before any deps get installed.
See cpython#104135.

cpython merged the iterate-and-skip variant of
``_load_windows_store_certs`` into ``Lib/ssl.py`` for the 3.11 branch
but never backported it to 3.10 (security-only). The salt-runtime
work-around dwoz landed in ``salt/__init__.py`` cannot help here -
salt is not yet importable in the CI-Deps venv. Dropping this file
into the onedir's ``Lib/site-packages`` makes Python apply the same
fix at interpreter start-up, before pip's TLS code runs.

Python-3.10-only: self-disables on Python 3.11+ (whose stdlib already
has the upstream fix). Delete this file together with the
``salt/__init__.py`` block and the ``salt/ext/tornado/netutil.py``
``sys.platform == 'win32'`` special-case on any branch whose onedir
Python is >= 3.11.
"""

import sys

if sys.platform == "win32" and sys.version_info < (3, 11):
    import ssl as _ssl

    # _SSLError captured as a default-arg so this stays callable after the
    # surrounding names go out of scope.
    def _salt_safe_load_windows_store_certs(
        self, storename, purpose, _SSLError=_ssl.SSLError
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

    _ssl.SSLContext._load_windows_store_certs = _salt_safe_load_windows_store_certs
