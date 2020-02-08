{% set tmp_dir = pillar['tmp_dir'] %}

private_key:
  x509.private_key_managed:
    - name: {{ tmp_dir }}/self.key

self_signed_cert:
  x509.certificate_managed:
    - name: {{ tmp_dir }}/self.crt
    - signing_private_key: {{ tmp_dir }}/self.key
    - CN: localhost
    - days_valid: 30
    - days_remaining: 0
    - require:
      - x509: private_key
