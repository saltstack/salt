include:
  - apps.pyopenssl

/etc/pki:
  file.directory:
    - user: root
    - group: root
    - mode: 700

/etc/pki/ca.key:
  x509.private_key_managed:
    - bits: 4096
    - backup: True

/etc/pki/ca.crt:
  x509.certificate_managed:
    - properties:
        signing_private_key: /etc/pki/ca.key
        subject:
          CN: ca.example.com
          C: US
          ST: Utah
          L: Salt Lake City
        extensions:
          - basicConstraints: 
              value: "CA:true"
              critical: True
          - keyUsage: 
              value: "cRLSign, keyCertSign"
              critical: True
          - subjectKeyIdentifier:
              value: hash
          - authorityKeyIdentifier:
              value: keyid,issuer:always
        days_valid: 3650
    - days_remaining: 0
    - backup: True
    - require:
      - x509: /etc/pki/ca.key

/etc/pki/ca.crl:
  x509.crl_managed:
    - signing_private_key: /etc/pki/ca.key
    - signing_cert: /etc/pki/ca.crt
    - revoked:
      - compromized_Web_key:
        - certificate: /etc/pki/ca.crt
        - revocation_date: 2015-03-01 00:00:00
        - reason: keyCompromise
      - terminated_vpn_user:
        - serial_number: D6:D2:DC:D8:4D:5C:C0:F4
        - not_after: 2016-01-01 00:00:00
        - revocation_date: 2015-02-25 00:00:00
        - reason: cessationOfOperation

/etc/pki/signing_policy.yml:
  file.managed:
        - source: salt://signing_policy.yml

mine.send:
  module.run: 
    - func: x509.get_pem_entries
    - kwargs:
        glob_path: /etc/pki/ca.crt
    - onchanges:
      - x509: /etc/pki/ca.crt

/etc/pki/ca-recv.crt:
  x509.pem_managed:
    - text: {{ salt['mine.get']('pki', 'x509.get_pem_entries')['pki']['/etc/pki/ca.crt']|replace('\n', '')|default('unavailable') }}

/etc/pki/www.key:
  x509.private_key_managed:
    - bits: 4096

/etc/pki/www.crt:
  x509.request_certificate_managed:
    - ca_server: pki
    - signing_policy: www
    - signing_cert: /etc/pki/ca-recv.crt
    - properties:
        public_key: /etc/pki/www.key
    - with_grains:
      - fqdn
    - days_remaining: 90
