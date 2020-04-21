test_priv_key:
  x509.private_key_managed:
    - name: {{ pillar['keyfile'] }}
    - bits: 4096

test_crt:
  x509.certificate_managed:
    - name: {{ pillar['crtfile'] }}
    - public_key: {{ pillar['keyfile'] }}
    - ca_server: minion
    - signing_policy: {{ pillar['signing_policy'] }}
    - CN: {{ grains.get('id') }}
    - days_remaining: 30
    - backup: True
    - require:
        - test_priv_key
