Transport TLS Support
=====================

Whenever possible transports should provide TLS Support. Currently the :doc:`tcp` and
:doc:`ws` transports support encryption and verification using TLS.

.. versionadded:: 2016.11.1

The TCP transport allows for the master/minion communication to be optionally
wrapped in a TLS connection. Enabling this is simple, the master and minion need
to be using the tcp connection, then the ``ssl``  option is enabled. The ``ssl``
option is passed as a dict and roughly corresponds to the options passed to the
Python `ssl.wrap_socket <https://docs.python.org/3/library/ssl.html#ssl.wrap_socket>`_
function for backwards compatibility.

.. versionadded:: 3007.0

The ``ssl`` option accepts ``verify_locations`` and ``verify_flags``. The
``verify_locations`` option is a list of strings or dictionaries. Strings are
passed as a single argument to the SSL context's ``load_verify_locations``
method. Dictionary keys are expected to be one of ``cafile``, ``capath``,
``cadata``. For each corresponding key, the key and value will be passed as a
keyword argument to ``load_verify_locations``. The ``verify_flags`` option is
a list of string names of verification flags which will be set on the SSL
context. All paths are assumed to be the full path to the file or directory.

A simple setup looks like this, on the Salt Master add the ``ssl`` option to the
master configuration file:

.. code-block:: yaml

    ssl:
      keyfile: <path_to_keyfile>
      certfile: <path_to_certfile>

A more complex setup looks like this, on the Salt Master add the ``ssl``
option to the master's configuration file. In this example the Salt Master will
require valid client side certificates from Minions by setting ``cert_reqs`` to
``CERT_REQUIRED``. The Salt Master will also check the certificate revocation
list named by ``crlfile`` (see :ref:`tls-certificate-revocation`):

.. code-block:: yaml

    ssl:
      keyfile: <path_to_keyfile>
      certfile: <path_to_certfile>
      cert_reqs: CERT_REQUIRED
      verify_locations:
        - <path_to_ca_cert>
        - capath: <directory_of_certs>
      crlfile: <path_to_crl>


The minimal `ssl` option in the minion configuration file looks like this:

.. code-block:: yaml

    ssl: True
    # Versions below 2016.11.4:
    ssl: {}

A Minion can be configured to present a client certificate to the master like this:

.. code-block:: yaml

    ssl:
      keyfile: <path_to_keyfile>
      certfile: <path_to_certfile>

Specific options can be sent to the minion also, as defined in the Python
`ssl.wrap_socket` function.

.. _tls-custom-pki:

Using a custom (enterprise) PKI
===============================

.. versionchanged:: 3008.4

Mutual TLS with certificates issued by an internal certificate authority works
with the ``tcp`` and ``ws`` transports.  The following rules apply:

**Trust anchors are exclusive.**  When ``ca_certs`` or ``verify_locations`` is
configured, those certificates are the *only* trust anchors.  Python's default
trust store (the system store or the bundled ``certifi`` CAs) is not consulted
in addition, so a publicly trusted CA can never issue a certificate that the
master accepts from a minion or that a minion accepts from a master.  To trust
the operating system store instead, leave ``ca_certs``/``verify_locations``
unset and enable ``use_os_truststore``.

**Intermediate CAs.**  Put the full issuing chain (leaf first, then every
intermediate) in ``certfile`` so the peer can build a path to the root in
``ca_certs``.  If only the intermediate is distributed as the trust anchor, add
``VERIFY_X509_PARTIAL_CHAIN`` to ``verify_flags``:

.. code-block:: yaml

    ssl:
      certfile: /etc/pki/tls/certs/salt-minion.chain.crt   # leaf + intermediates
      keyfile: /etc/pki/tls/private/salt-minion.key
      ca_certs: /etc/pki/tls/certs/corp-issuing-ca.crt     # intermediate only
      cert_reqs: CERT_REQUIRED
      verify_flags:
        - VERIFY_X509_PARTIAL_CHAIN

**Hostname verification uses the configured master name.**  Minions resolve
``master`` to an IP address before connecting.  The TLS layer nevertheless
verifies the master certificate against the *configured* ``master`` hostname,
so the certificate only needs a DNS Subject Alternative Name for that name; an
IP SAN is required only when ``master`` is itself an IP address.  When the
name the certificate carries differs from the address Salt connects to (load
balancers, split DNS, the master-local ``salt``/``salt-run``/``salt-api``
clients, which connect to ``interface`` and have no ``master`` setting), pin
the expected name:

.. code-block:: yaml

    ssl:
      server_hostname: salt-master.corp.example

.. note::
    Upgrade note: releases before 3008.4 verified the master certificate
    against the *resolved IP address*.  A deployment whose master certificate
    carries only an IP SAN while minions use ``master: <hostname>`` keeps
    working by pinning that IP on the minions (``ssl.server_hostname:
    <master ip>``) or by reissuing the certificate with a DNS SAN.

**Key usage.**  Minion certificates need the ``clientAuth`` extended key usage;
the master certificate needs ``serverAuth``.  Master-local tooling (``salt``,
``salt-run``, ``salt-api``, the ``salt-master`` maintenance processes) connects
to the master's own request server as a TLS *client*.  By default it presents
``certfile``, which therefore also needs ``clientAuth`` and a SAN covering the
``interface`` address.  With a strict PKI profile that issues ``serverAuth``-only
server certificates, give the master a dedicated client certificate instead:

.. code-block:: yaml

    ssl:
      certfile: /etc/pki/tls/certs/salt-master.chain.crt      # serverAuth
      keyfile: /etc/pki/tls/private/salt-master.key
      client_certfile: /etc/pki/tls/certs/salt-master-client.chain.crt  # clientAuth
      client_keyfile: /etc/pki/tls/private/salt-master-client.key
      server_hostname: salt-master.corp.example
      ca_certs: /etc/pki/tls/certs/corp-root.crt
      cert_reqs: CERT_REQUIRED

``client_certfile``/``client_keyfile`` are only used for outgoing (client side)
connections and fall back to ``certfile``/``keyfile`` when unset.  They may also
be set on minions.

**Worker pools.**  The internal link between the master's request router and
its worker pools is a local IPC connection and is never wrapped in TLS, so
mutual TLS works with the default ``worker_pools_enabled: True``.

.. _tls-certificate-rotation:

Certificate rotation
--------------------

.. versionadded:: 3008.4

Rotated certificates are picked up without restarting ``salt-master`` or
``salt-minion``.  Every ``reload_interval`` seconds (default 60; ``0``
disables the background poll) the daemons compare the files named in ``ssl``
-- ``certfile``, ``keyfile``, ``client_certfile``, ``client_keyfile``,
``ca_certs``, the ``verify_locations`` files and directories and the
``crlfile`` CRLs -- with what is loaded.  Clients always re-check before opening a new connection, whatever
the interval.  The files are copied to a private directory first and the copy
is what gets validated and loaded, so a rotation tool rewriting the originals
mid-check cannot get unvalidated material served.

New material is *validated before it is adopted*:

* the certificate and key must load and belong together;
* the certificate must be valid for the current time;
* when verification is enabled (``cert_reqs`` other than ``CERT_NONE``, the
  default for the master and the documented mutual-TLS setup) the certificate
  must chain to the configured trust anchors and carry the right extended key
  usage for its role (``serverAuth`` for ``certfile`` on the master,
  ``clientAuth`` for minion certificates and ``client_certfile``).  A
  time-valid *self-signed* certificate is accepted only when verification is
  disabled.

The chain check verifies the daemon's *own* certificate against the anchors
it uses for *peers*, which assumes one PKI issues both.  Deployments with
separate server and client CAs (the master trusts the client CA, minions
trust the server CA) must set ``reload_verify_chain: False``: rotation then
still requires a matching key and a time-valid certificate, but no chain
verification.

The files are validated from a private snapshot (a ``0700`` directory of
``0600`` copies under the system temporary directory) so the bytes checked are
the bytes loaded; the snapshot is removed after every check, and only a process
killed mid-check can leave one behind.

Material that fails these checks is logged at ERROR level once and ignored;
the certificate already in use stays active until the files change again.
Rotate the key and the certificate as a pair (write both, then move them into
place) -- a half-written rotation is simply rejected until the pair matches.

Listening sockets keep serving while the certificate is swapped underneath
them, so no connection is dropped.  Clients use the new certificate on their
next connection.  Trust anchors *added* to ``ca_certs`` take effect on the
master immediately; anchors *removed* from it stay trusted by a running master
until restart (OpenSSL cannot unload certificates from a live store) -- the
master logs a warning whenever the anchor set changes on rotation so that a
retired or compromised CA is not assumed gone.  Minions rebuild their context,
so removals apply to them at the next connection.

A rotated *server* certificate is checked for chain, validity and purpose; its
*name* is checked only against a pinned ``ssl.server_hostname`` (the daemon
cannot know which name its peers verify, and a name read from the certificate
itself would match trivially).  Pin the name on the master so a certificate
issued for the wrong host is rejected at rotation rather than discovered by
every minion at its next connection.

.. code-block:: yaml

    ssl:
      certfile: /etc/pki/tls/certs/salt-master.chain.crt
      keyfile: /etc/pki/tls/private/salt-master.key
      ca_certs: /etc/pki/tls/certs/corp-root.crt
      cert_reqs: CERT_REQUIRED
      reload_interval: 30
      reload_verify_chain: True

.. _tls-certificate-revocation:

Certificate revocation
----------------------

.. versionadded:: 3008.4

``crlfile`` names one PEM file, or a list of PEM files, holding certificate
revocation lists (a file may hold several CRLs; one CRL per issuing CA is the
usual layout).  A ``crlfile`` must contain PEM encoded CRLs and nothing else:
a file that also holds a certificate or any other data is refused (the daemon
does not start, and a refresh like that is rejected), so the file written by
a CRL refresh job can never add a trust anchor.  Only the parsed CRLs are
handed to OpenSSL.  When it is set the CRLs are loaded into the TLS context and
``VERIFY_CRL_CHECK_LEAF`` is enabled, so a peer whose certificate is listed
is refused during the TLS handshake.  It works on both sides: on the master
it checks minion (client) certificates, on a minion it checks the master
certificate.  The master-local clients (``salt``, ``salt-run``, ``salt-api``)
read the master's ``ssl`` settings and verify the master's own certificate
with the same CRLs, so on the master ``crlfile`` must also cover the CA that
issued ``certfile``.  ``verify_flags`` adds to it; ``VERIFY_CRL_CHECK_CHAIN`` checks
every certificate of the chain and then needs a current CRL for every CA in
it, root included.

.. code-block:: yaml

    ssl:
      certfile: /etc/pki/tls/certs/salt-master.chain.crt
      keyfile: /etc/pki/tls/private/salt-master.key
      ca_certs: /etc/pki/tls/certs/corp-root.crt
      cert_reqs: CERT_REQUIRED
      crlfile: /etc/pki/tls/crl/corp-issuing-ca.crl.pem
      # or several CRLs, and the whole chain checked:
      # crlfile:
      #   - /etc/pki/tls/crl/corp-root-ca.crl.pem
      #   - /etc/pki/tls/crl/corp-issuing-ca.crl.pem
      # verify_flags:
      #   - VERIFY_CRL_CHECK_CHAIN

CRL checking fails closed: once enabled, a peer certificate is refused when
no current CRL from its issuer is loaded ("unable to get certificate CRL")
or when that CRL has passed its ``nextUpdate`` ("CRL has expired").  Keep the
CRLs refreshed well before ``nextUpdate``.

CRLs are typically refreshed every few hours by an external job; the daemons
pick a refreshed ``crlfile`` up without a restart, with the same polling and
validation as :ref:`certificate rotation <tls-certificate-rotation>`.  A
refreshed CRL is adopted only when it parses, is current (``thisUpdate`` <=
now <= ``nextUpdate``), is signed by its issuer and is newer (later
``thisUpdate``) than the current CRL in use for the same CA.  The signature
check is mandatory, so the certificate of every CA that signs a configured
CRL must be available to the daemon: in ``ca_certs``, in a
``verify_locations`` file or ``capath`` directory, or in its own
``certfile`` chain.  For a CRL issued by an intermediate CA that peers send
in their chain, add the intermediate certificate to ``verify_locations``.

A refreshed CRL that fails these checks is logged at ERROR level once and the
*last good CRL stays in use*, exactly like a rejected certificate rotation.
Keeping the last good CRL never extends it past its ``nextUpdate``: when it
expires without a valid replacement every peer of that CA is refused, and
that is logged at ERROR level as well.  A CRL whose ``thisUpdate`` is still
in the future (clock skew between the CA and the host) is re-checked at every
poll and adopted as soon as it is valid.  Write a refreshed CRL to a
temporary file and rename it into place.

CRLs and certificates are validated independently: a valid certificate
rotation is adopted together with the CRL in use even while a CRL refresh is
being rejected, and a valid CRL refresh is adopted while a certificate
rotation is being rejected.  A rotated certificate that a CRL in use revokes
is rejected; a refreshed CRL that revokes the daemon's current certificate is
adopted and logged at ERROR level (rotate the certificate).  The validation of the daemon's own rotated certificate does not
apply the OpenSSL CRL *check* (the CRLs are for the peers and need not cover
the daemon's own CA); revocation of the daemon's own certificate is checked
by serial number instead.

A refreshed CRL is added to the running TLS context, where the most recent
current CRL of each CA is the one used.  Superseded CRLs stay in memory until
the daemon restarts, so memory grows by about the size of the CRL with every
refresh: a 100 KB CRL refreshed every four hours adds about 600 KB a day, a
few KB CRL a negligible amount.  Only CRLs that actually changed are added.

A refused handshake is logged by the master once per peer address and reason
per hour, with a hint, rather than once per connection attempt: a revoked
minion logs a WARNING naming its address, a problem with the master's own CRL
setup (missing, expired or not yet valid CRL, bad CRL signature) an ERROR.
The ``ws`` transport cannot see the peer address at that point and logs the
reason without it.

Loading a CRL through ``verify_locations`` together with a
``VERIFY_CRL_CHECK_*`` flag still works, but such CRLs are treated as trust
anchors: they are not validated on reload and, on the master, every refresh logs the
"trust anchors changed" warning.  Use ``crlfile`` instead.

.. _tls-encryption-optimization:

TLS Encryption Optimization
===========================

.. versionadded:: 3008.0

When TLS is configured with mutual authentication (``cert_reqs: CERT_REQUIRED``),
the application-layer AES encryption becomes redundant. Salt 3008.0 introduces
an optional TLS encryption optimization that eliminates this redundant encryption,
improving performance while maintaining security.

Overview
--------

Salt traditionally performs double encryption:

1. **Application layer**: AES-192/256-CBC + HMAC-SHA256 (via Crypticle)
2. **Transport layer**: TLS 1.2+ (when configured)

With the TLS optimization enabled, Salt skips the application-layer AES encryption
when all security requirements are met, relying solely on TLS for encryption.

Configuration
-------------

To enable TLS encryption optimization, set ``disable_aes_with_tls`` to ``True``
in both master and minion configurations:

**Master configuration** (``/etc/salt/master.d/tls_optimization.conf``):

.. code-block:: yaml

    transport: tcp  # or 'ws' for WebSocket

    ssl:
      certfile: /etc/pki/tls/certs/salt-master.crt
      keyfile: /etc/pki/tls/private/salt-master.key
      ca_certs: /etc/pki/tls/certs/ca-bundle.crt
      cert_reqs: CERT_REQUIRED  # Required for optimization

    disable_aes_with_tls: true

**Minion configuration** (``/etc/salt/minion.d/tls_optimization.conf``):

.. code-block:: yaml

    transport: tcp  # Must match master

    ssl:
      certfile: /etc/pki/tls/certs/minion.crt
      keyfile: /etc/pki/tls/private/minion.key
      ca_certs: /etc/pki/tls/certs/ca-bundle.crt
      cert_reqs: CERT_REQUIRED  # Required for optimization

    disable_aes_with_tls: true

.. important::
    The minion certificate **must** contain the minion ID in either the
    Common Name (CN) or Subject Alternative Name (SAN) field to prevent
    impersonation attacks.

Requirements
------------

The TLS optimization requires all of the following conditions:

1. **Configuration opt-in**: ``disable_aes_with_tls: true`` on both master and minion
2. **SSL configured**: Valid ``ssl`` configuration dictionary
3. **Mutual authentication**: ``cert_reqs: CERT_REQUIRED``
4. **TLS transport**: Transport must be ``tcp`` or ``ws`` (not ``zeromq``)
5. **Valid certificates**: Properly signed certificates from trusted CA
6. **Certificate identity**: Minion certificates must contain minion ID in CN or SAN

If any requirement is not met, Salt automatically falls back to standard AES encryption.

Certificate Identity Requirement
--------------------------------

To prevent minion impersonation attacks, minion certificates must contain the
minion ID. This can be done in two ways:

**Option 1: Minion ID in Common Name (CN)**

.. code-block:: bash

    # Get minion ID
    minion_id=$(salt-call --local grains.get id --out=txt | cut -d: -f2 | tr -d ' ')

    # Generate certificate with minion ID in CN
    openssl req -new -key minion.key -out minion.csr \
      -subj "/C=US/O=MyOrg/CN=$minion_id"

**Option 2: Minion ID in Subject Alternative Name (SAN)**

.. code-block:: bash

    # Create SAN configuration
    cat > san.cnf <<EOF
    [req]
    distinguished_name = req_distinguished_name
    req_extensions = v3_req

    [req_distinguished_name]

    [v3_req]
    subjectAltName = @alt_names

    [alt_names]
    DNS.1 = $minion_id
    DNS.2 = localhost
    IP.1 = 127.0.0.1
    EOF

    # Generate certificate with SAN
    openssl req -new -key minion.key -out minion.csr \
      -config san.cnf \
      -subj "/C=US/O=MyOrg/CN=$minion_id"

Verify certificate identity:

.. code-block:: bash

    # Check Common Name
    openssl x509 -in minion.crt -noout -subject

    # Check Subject Alternative Name
    openssl x509 -in minion.crt -noout -text | grep -A 1 "Subject Alternative Name"

Performance Impact
------------------

Expected performance improvements when TLS optimization is enabled:

- **Command latency**: 10-25% reduction
- **Encryption CPU usage**: 30-50% reduction
- **Greatest impact**: Large payloads and high-throughput environments

Example performance test:

.. code-block:: bash

    # Before enabling optimization
    time salt '*' test.ping

    # After enabling optimization
    time salt '*' test.ping

    # Expect 10-25% improvement

Security Considerations
-----------------------

The TLS encryption optimization maintains security because:

- **TLS provides equivalent encryption**: TLS 1.2+ with AES-128/256-GCM provides
  the same or better security properties as application-layer AES-CBC
- **Certificate validation**: TLS validates certificates and prevents MITM attacks
- **Identity verification**: Certificate identity matching prevents impersonation
- **Automatic fallback**: System falls back to AES if requirements not met
- **Backward compatible**: Works with non-optimized Salt installations

Verification
------------

To verify the optimization is active:

**On Master:**

.. code-block:: bash

    # Check configuration
    salt-run config.get disable_aes_with_tls

    # Check logs for optimization messages
    grep "TLS optimization" /var/log/salt/master

**On Minion:**

.. code-block:: bash

    # Check configuration
    salt-call config.get disable_aes_with_tls

    # Verify certificate contains minion ID
    salt-call grains.get id
    openssl x509 -in /etc/pki/tls/certs/minion.crt -noout -subject

Troubleshooting
---------------

**Issue: Optimization not activating**

Check all requirements:

.. code-block:: bash

    # Verify configuration
    salt-call config.get disable_aes_with_tls  # Should be True
    salt-call config.get transport              # Should be 'tcp' or 'ws'
    salt-call config.get ssl:cert_reqs          # Should be CERT_REQUIRED

    # Verify certificate identity
    salt-call grains.get id  # Get minion ID
    openssl x509 -in /path/to/cert.crt -noout -subject  # Check CN
    openssl x509 -in /path/to/cert.crt -noout -text | \
      grep -A1 "Subject Alternative Name"  # Check SAN

**Issue: Certificate identity mismatch**

Regenerate certificate with correct minion ID (see Certificate Identity Requirement above).

Rollback
--------

To disable the optimization:

.. code-block:: yaml

    # Set to false or remove the option
    disable_aes_with_tls: false

Restart services:

.. code-block:: bash

    # Master
    systemctl restart salt-master

    # Minions
    systemctl restart salt-minion

Compatibility
-------------

The TLS optimization is fully backward compatible:

+----------------------------+----------------------------+---------------------------+
| Master                     | Minion                     | Result                    |
+============================+============================+===========================+
| Optimized (3008.0+)        | Optimized (3008.0+)        | TLS optimization active   |
+----------------------------+----------------------------+---------------------------+
| Optimized (3008.0+)        | Standard (any version)     | AES encryption used       |
+----------------------------+----------------------------+---------------------------+
| Standard (any version)     | Optimized (3008.0+)        | AES encryption used       |
+----------------------------+----------------------------+---------------------------+
| Old version                | New version                | AES encryption used       |
+----------------------------+----------------------------+---------------------------+

See Also
--------

- :doc:`tcp` - TCP Transport documentation
- :doc:`ws` - WebSocket Transport documentation
- :ref:`Configuration Reference <configuration-salt-master>` - Master configuration options
