{% set keyfile = pillar['keyfile'] %}
{% set crtfile = pillar['crtfile'] %}

private_key:
  x509.private_key_managed:
    - name: {{ keyfile }}

self_signed_cert:
  x509.certificate_managed:
    - name: {{ crtfile }}
    - signing_private_key: {{ keyfile }}
    - CN: localhost
    - days_valid: 30
    - days_remaining: 0
    - require:
      - x509: private_key
