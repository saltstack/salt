test_crt:
  x509.certificate_managed:
    - name: {{ pillar['crtfile'] }}
    - ca_server: minion
    - signing_policy: {{ pillar['signing_policy'] }}
    - CN: minion
    - days_remaining: 30
    - backup: True
    - managed_private_key:
        name: {{ pillar['keyfile'] }}
        bits: 4096
        backup: True
