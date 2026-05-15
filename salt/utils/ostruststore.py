"""
Utility functions for OS-native TLS certificate store support.

When ``use_os_truststore: True`` is set in the Salt master or minion
configuration, Salt calls :func:`apply_if_enabled` once at daemon startup.
That function uses the ``truststore`` library to monkey-patch Python's
``ssl.SSLContext`` so that every subsequent TLS connection verifies against
the native OS certificate store instead of the bundled ``certifi`` CA bundle:

- **Windows** — Local Machine Certificate Store (accessed via CryptoAPI)
- **macOS** — Keychain
- **Linux** — ``/etc/ssl/certs`` or ``/etc/pki/tls``

The injection is process-global and one-shot; calling :func:`apply_if_enabled`
more than once is safe (idempotent).

.. note::

    This has no effect on Salt's master/minion PKI authentication layer
    (``pki_dir``, AES session keys, minion key acceptance).  It only affects
    outbound HTTPS/TLS connections — HTTP runner, gitfs, fileserver backends,
    cloud drivers, ``salt.utils.http.query``, etc.

.. note::

    ``truststore`` requires Python 3.10 or newer.  On older Python the package
    is not installed and ``use_os_truststore`` will log a warning and fall back
    to the default ``certifi`` bundle.

.. note::

    On Windows the ``LocalSystem`` service account (the default for the
    salt-master and salt-minion Windows services) only has access to the
    **Local Machine** store, not the Current User store.  Certificates
    deployed via Group Policy to the Local Machine store are visible;
    certificates installed only in a user's personal store are not.

.. warning::

    On Windows, certificate verification is performed via a CryptoAPI service
    call rather than a simple file read.  This may introduce a small amount of
    extra latency on the first TLS connection made by a new process.  On Linux
    and macOS the performance impact is negligible.

.. warning::

    Do **not** install ``pip-system-certs`` into the Salt Python environment.
    That package installs a ``.pth`` file that unconditionally activates the OS
    trust store on every Python startup, before Salt reads its configuration.
    This bypasses the ``use_os_truststore`` setting entirely.  Use the
    ``truststore`` package instead, which Salt controls explicitly.
"""

import logging

log = logging.getLogger(__name__)

try:
    import truststore as _truststore

    HAS_TRUSTSTORE = True
except ImportError:
    _truststore = None  # always defined so patch.object() works in tests
    HAS_TRUSTSTORE = False

# Module-level flag so we never inject more than once per process.
_injected = False


def apply_if_enabled(opts):
    """
    Inject OS-native certificate store support when ``use_os_truststore`` is
    enabled in *opts*.

    Safe to call multiple times — only the first call with a truthy
    ``use_os_truststore`` triggers the injection.

    :param dict opts: Salt master or minion configuration dictionary.
    """
    global _injected

    if not opts.get("use_os_truststore", False):
        return

    if _injected:
        return

    if not HAS_TRUSTSTORE:
        log.warning(
            "use_os_truststore is enabled but the 'truststore' package is not "
            "installed.  SSL connections will continue to use the bundled "
            "certifi CA bundle.  Install truststore (Python 3.10+) to enable "
            "OS trust store support."
        )
        return

    try:
        _truststore.inject_into_ssl()
        _injected = True
        log.debug("OS trust store injected via truststore")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log.error(
            "Failed to inject OS trust store via truststore: %s", exc
        )  # pragma: no cover


def is_injected():
    """
    Return ``True`` if the OS trust store has been successfully injected into
    Python's SSL layer for this process.

    :rtype: bool
    """
    return _injected


def active_store_name(opts):
    """
    Return a short string identifying which CA store is active.

    Returns ``"os"`` when the OS trust store injection succeeded and
    ``use_os_truststore`` is enabled in *opts*; otherwise returns
    ``"certifi"``.

    This value is exposed as the ``ca_truststore`` grain.

    :param dict opts: Salt master or minion configuration dictionary.
    :rtype: str
    """
    if _injected and opts.get("use_os_truststore", False):
        return "os"
    return "certifi"
