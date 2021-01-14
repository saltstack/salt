{% set keyfile = pillar['keyfile'] %}
{% set crtfile = pillar['crtfile'] %}
{% set user = pillar['user'] %}

private_key:
  x509.private_key_managed:
    - name: {{ keyfile }}

self_signed_cert:
  x509.certificate_managed:
    - name: {{ crtfile }}
    # crtfile is many folders deep, so this line will cause
    # file.managed to fail
    - makedirs: False
    - signing_private_key: {{ keyfile }}
    - CN: localhost
    - days_valid: 90
    - days_remaining: 30
    - require:
      - x509: private_key
