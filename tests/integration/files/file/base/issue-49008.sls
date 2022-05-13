{{ pillar['crtfile'] }}:
  x509.certificate_managed:
    - signing_private_key: {{ pillar['keyfile'] }}
    - CN: testy-mctest
    - basicConstraints: "critical CA:true"
    - keyUsage: "critical cRLSign, keyCertSign"
    - subjectKeyIdentifier: hash
    - authorityKeyIdentifier: keyid,issuer:always
    - days_valid: 1460
    - days_remaining: 0
    - backup: True
    - watch:
      - x509: {{ pillar['keyfile'] }}

{{ pillar['keyfile'] }}:
  x509.private_key_managed:
    - bits: 4096
    - backup: True
