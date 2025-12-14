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
function for backwards compatability.

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
``CERT_REQUIRED``. The Salt Master will also check a certificate revocation list
if one is provided in ``verify_locations``:

.. code-block:: yaml

    ssl:
      keyfile: <path_to_keyfile>
      certfile: <path_to_certfile>
      cert_reqs: CERT_REQUIRED
      verify_locations:
        - <path_to_ca_cert>
        - capath: <directory_of_certs>
        - cafile: <path_to_crl>
      verify_flags:
        - VERIFY_CRL_CHECK_CHAIN


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

.. _tls-encryption-optimization:

TLS Encryption Optimization
============================

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
---------------------------------

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
