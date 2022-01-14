{% set keyfile = pillar['keyfile'] %}
{% set crtfile = pillar['crtfile'] %}
{% set subjectAltName = pillar['subjectAltName']|default('DNS:alt.service.local') %}
{% set fileMode = pillar['fileMode']|default('0600') %}

private_key:
  x509.private_key_managed:
    - name: {{ keyfile }}

self_signed_cert:
  x509.certificate_managed:
    - name: {{ crtfile }}
    - mode: {{ fileMode }}
    - signing_private_key: {{ keyfile }}
    - CN: service.local
    - subjectAltName: {{ subjectAltName }}
    - days_valid: 90
    - days_remaining: 30
    - require:
      - x509: private_key
