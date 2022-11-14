{% set tmp_dir = pillar['tmp_dir'] %}

{{ tmp_dir }}/pki:
  file.directory: []

{{ tmp_dir }}/pki/issued_certs:
  file.directory: []

{{ tmp_dir }}/pki/ca.key:
  x509.private_key_managed:
    - bits: 4096
    - require:
      - file: {{ tmp_dir }}/pki

{{ tmp_dir }}/pki/ca.crt:
  x509.certificate_managed:
    - signing_private_key: {{ tmp_dir }}/pki/ca.key
    - CN: ca.example.com
    - C: US
    - ST: Utah
    - L: Salt Lake City
    - basicConstraints: "critical CA:true"
    - keyUsage: "critical cRLSign, keyCertSign"
    - subjectKeyIdentifier: hash
    - authorityKeyIdentifier: keyid,issuer:always
    - days_valid: 3650
    - days_remaining: 0
    - backup: True
    - require:
      - file: {{ tmp_dir }}/pki
      - {{ tmp_dir }}/pki/ca.key

{{ tmp_dir }}/pki/test.key:
  x509.private_key_managed:
    - bits: 1024
    - backup: True

test_crt:
  x509.certificate_managed:
    - name: {{ tmp_dir }}/pki/test.crt
    - ca_server: minion
    - signing_policy: ca_policy
    - public_key: {{ tmp_dir }}/pki/test.key
    - CN: minion
    - days_remaining: 30
    - backup: True
    - require:
        - {{ tmp_dir }}/pki/ca.crt
        - {{ tmp_dir }}/pki/test.key

#mine.send:
#  module.run:
#    - func: x509.get_pem_entries
#    - kwargs:
#        glob_path: {{ tmp_dir }}/pki/ca.crt
#    - onchanges:
#      - x509: {{ tmp_dir }}/pki/ca.crt

{{ tmp_dir }}/pki/ca.crl:
  x509.crl_managed:
    - signing_private_key: {{ tmp_dir }}/pki/ca.key
    - signing_cert: {{ tmp_dir }}/pki/ca.crt
    - digest: sha512
    - revoked:
      - compromized_Web_key:
        - certificate: {{ tmp_dir }}/pki/test.crt
        - revocation_date: 2015-03-01 00:00:00
        - reason: keyCompromise
      #- terminated_vpn_user:
      #  - serial_number: D6:D2:DC:D8:4D:5C:C0:F4
      #  - not_after: 2016-01-01 00:00:00
      #  - revocation_date: 2015-02-25 00:00:00
      #  - reason: cessationOfOperation
    - require:
      - x509: {{ tmp_dir }}/pki/ca.crt
      - x509: test_crt
