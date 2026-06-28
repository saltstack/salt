"""
Salt package
"""

import asyncio
import importlib
import os
import re
import sys
import warnings

# Aweful hack to keep salt-ssh tests passing with tornado >=6.4.2. Salt ssh
# needs to be transitioned to use a relenv environemnt by default. This should
# be removed when salt-ssh uses relenv or we no longer want salt-ssh to support
# older system python versions <3.8
if not hasattr(re, "Match"):
    re.Match = object()


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Work around cpython#104135 on Windows: ssl._load_windows_store_certs feeds
# every cert in the OS root store to load_verify_locations(cadata=...) as one
# blob, so a single ASN.1-malformed cert aborts the whole load. OpenSSL 3.5.x
# (shipped by relenv >= 0.22.13) is strict enough to reject certs the prior
# OpenSSL accepted, which breaks ssl.create_default_context() at import time
# for salt and for any third-party lib (aiohttp, requests, urllib3, tornado,
# ...) running under the salt onedir on Windows. Replace the loader with the
# iterate-and-skip variant proposed upstream.
#
# Needed on Python 3.10 and 3.11: cpython merged the iterate-and-skip fix
# into Lib/ssl.py for the 3.12 branch but never backported it to 3.10
# (security-only) or 3.11. The 3007.x onedir ships Python 3.10 via relenv;
# 3008.x and later use Python 3.14, whose stdlib already has the upstream
# fix. DO NOT forward-merge this block to a branch whose onedir Python is
# >= 3.12 - delete it instead.
#
# DURABLE CLEANUP: the right home for this patch is relenv's cpython build
# (one patch_file call against Lib/ssl.py during build) - once a relenv
# release carrying it lands in this branch's onedir, drop this block and
# cicd/windows-ssl-104135-patch.py + the Patch-Lib/ssl.py steps in
# .github/workflows/{build-deps-ci,test,test-packages}-action.yml's Windows
# jobs.
if sys.platform == "win32":
    import ssl as _ssl

    # _SSLError is captured as a default-arg so this stays callable after
    # the surrounding names are deleted at the bottom of this block.
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
    del _ssl, _salt_safe_load_windows_store_certs


class NaclImporter:
    """
    Import hook to force PyNaCl to perform dlopen on libsodium with the
    RTLD_DEEPBIND flag. This is to work around an issue where pyzmq does a dlopen
    with RTLD_GLOBAL which then causes calls to libsodium to resolve to
    tweetnacl when it's been bundled with pyzmq.

    See:  https://github.com/zeromq/pyzmq/issues/1878
    """

    loading = False

    def find_module(self, module_name, package_path=None):
        if not NaclImporter.loading and module_name.startswith("nacl"):
            NaclImporter.loading = True
            return self
        return None

    def create_module(self, spec):
        dlopen = hasattr(sys, "getdlopenflags")
        if dlopen:
            dlflags = sys.getdlopenflags()
            # Use RTDL_DEEPBIND in case pyzmq was compiled with ZMQ_USE_TWEETNACL. This is
            # needed because pyzmq imports libzmq with RTLD_GLOBAL.
            if hasattr(os, "RTLD_DEEPBIND"):
                flags = os.RTLD_DEEPBIND | dlflags
            else:
                flags = dlflags
            sys.setdlopenflags(flags)
        try:
            mod = importlib.import_module(spec.name)
        finally:
            if dlopen:
                sys.setdlopenflags(dlflags)
        NaclImporter.loading = False
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        return None


# Try our importer first
sys.meta_path = [NaclImporter()] + sys.meta_path


# All salt related deprecation warnings should be shown once each!
warnings.filterwarnings(
    "once",  # Show once
    "",  # No deprecation message match
    DeprecationWarning,  # This filter is for DeprecationWarnings
    r"^(salt|salt\.(.*))$",  # Match module(s) 'salt' and 'salt.<whatever>'
    # Do *NOT* add append=True here - if we do, salt's DeprecationWarnings will
    # never show up
)

# Filter the backports package UserWarning about being re-imported
warnings.filterwarnings(
    "ignore",
    "^Module backports was already imported from (.*), but (.*) is being added to sys.path$",
    UserWarning,
    append=True,
)

# Filter the setuptools UserWarning until we stop relying on distutils
warnings.filterwarnings(
    "ignore",
    message="Setuptools is replacing distutils.",
    category=UserWarning,
    module="_distutils_hack",
)

warnings.filterwarnings(
    "ignore",
    message="invalid escape sequence.*",
    category=DeprecationWarning,
)

warnings.filterwarnings(
    "ignore",
    "Deprecated call to `pkg_resources.declare_namespace.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    ".*pkg_resources is deprecated as an API.*",
    category=DeprecationWarning,
)

# Third-party libraries that salt's loader pulls in eagerly (boto modules
# via salt.utils.boto*, paramiko via salt-ssh, etc.) emit SyntaxWarning /
# CryptographyDeprecationWarning at *compile* time on Python 3.10.  They
# bypass the per-test ``recwarn`` plumbing and leak straight to ``stderr``,
# tripping CLI tests that gate on ``assert not cmd.stderr`` (e.g.
# ``tests/pytests/integration/cli/test_batch.py``).  Filter them here -
# before ``salt.loader`` triggers any of these imports - so the warnings
# never reach the subprocess stderr.
#
# Python's compile-time ``SyntaxWarning`` emission feeds
# ``PyErr_WarnExplicitObject`` with ``module=NULL`` -- ``warnings.warn``
# then derives ``__module__`` from the source filename's basename (e.g.
# ``connection`` for ``boto/iam/connection.py``).  A ``module=r"boto\..*"``
# regex therefore never matches; a category-only filter is the only
# reliable knob for compile-time warnings.  Salt itself does not produce
# ``SyntaxWarning`` (all in-tree files are linted by black/flake8), so
# silencing the category globally is safe.
warnings.filterwarnings(
    "ignore",
    category=SyntaxWarning,
)
# ``CryptographyDeprecationWarning`` subclasses ``UserWarning`` (not
# ``DeprecationWarning``) in cryptography>=37, so we cannot just gate
# on the DeprecationWarning category here.  Match by message text.
warnings.filterwarnings(
    "ignore",
    message=".*TripleDES has been moved.*",
)


def __define_global_system_encoding_variable__():
    import builtins
    import sys

    # Define the detected encoding as a built-in variable for ease of use
    setattr(builtins, "__salt_system_encoding__", sys.getdefaultencoding())

    # This is now garbage collectable
    del builtins
    del sys


__define_global_system_encoding_variable__()

# This is now garbage collectable
del __define_global_system_encoding_variable__

# Make sure Salt's logging tweaks are always present
# DO NOT MOVE THIS IMPORT
# pylint: disable=unused-import
import salt._logging  # isort:skip

# pylint: enable=unused-import
