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
