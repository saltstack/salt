:orphan:

==================================
Salt Release Notes - Codename Neon
==================================


Keystore State and Module
=========================

A new :py:func:`state <salt.states.keystore>` and
:py:func:`execution module <salt.modules.keystore>` for manaing Java
Keystore files is now included. It allows for adding/removing/listing
as well as managing keystore files.

.. code-block:: bash

  # salt-call keystore.list /path/to/keystore.jks changeit
  local:
    |_
      ----------
      alias:
          hostname1
      expired:
          True
      sha1:
          CB:5E:DE:50:57:99:51:87:8E:2E:67:13:C5:3B:E9:38:EB:23:7E:40
      type:
          TrustedCertEntry
      valid_start:
          August 22 2012
      valid_until:
          August 21 2017

.. code-block:: yaml

  define_keystore:
    keystore.managed:
      - name: /tmp/statestore.jks
      - passphrase: changeit
      - force_remove: True
      - entries:
        - alias: hostname1
          certificate: /tmp/testcert.crt
        - alias: remotehost
          certificate: /tmp/512.cert
          private_key: /tmp/512.key
        - alias: stringhost
          certificate: |
            -----BEGIN CERTIFICATE-----
            MIICEjCCAX
            Hn+GmxZA
            -----END CERTIFICATE-----
