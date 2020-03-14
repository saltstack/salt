test_crt:
  x509.certificate_managed:
    - name: {{ pillar['crtfile'] }}
    - ca_server: minion
    - signing_policy: restricted_policy
    - CN: minion
    - days_remaining: 30
    - backup: True
    - managed_private_key:
        name: {{ tmp_dir  }}/pki/test.key
        bits: 4096
        backup: True
