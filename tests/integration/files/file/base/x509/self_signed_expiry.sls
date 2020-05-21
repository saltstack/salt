{% set keyfile = pillar['keyfile'] %}
{% set crtfile = pillar['crtfile'] %}
{% set days_valid = pillar['days_valid'] %}
{% set days_remaining = pillar['days_remaining'] %}

private_key:
  x509.private_key_managed:
    - name: {{ keyfile }}

self_signed_cert:
  x509.certificate_managed:
    - name: {{ crtfile }}
    - signing_private_key: {{ keyfile }}
    - CN: localhost
    - days_valid: {{ days_valid }}
    - days_remaining: {{ days_remaining }}
    - require:
      - x509: private_key
