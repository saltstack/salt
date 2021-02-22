{% set tmp_dir = pillar['tmp_dir'] %}

{{ tmp_dir }}/pki:
  file.directory

{{ tmp_dir  }}/pki/issued_certs:
  file.directory

{{ tmp_dir  }}/pki/ca.key:
  x509.private_key_managed:
    # speed this up
    - bits: 1024
    - require:
      - file: {{ tmp_dir }}/pki

{{ tmp_dir  }}/pki/ca.crt:
  x509.certificate_managed:
    - signing_private_key: {{ tmp_dir  }}/pki/ca.key
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
      - file: {{ tmp_dir  }}/pki
      - x509: {{ tmp_dir  }}/pki/ca.key

{{ tmp_dir  }}/pki/test.key:
  x509.private_key_managed:
    # speed this up
    - bits: 1024
    - backup: True

test_crt:
  x509.certificate_managed:
    - name: {{ tmp_dir  }}/pki/test.crt
    - ca_server: minion
    - signing_policy: ca_policy
    - public_key: {{ tmp_dir  }}/pki/test.key
    - CN: minion
    - days_remaining: 30
    - backup: True
    - require:
        - x509: {{ tmp_dir  }}/pki/ca.crt
        - x509: {{ tmp_dir  }}/pki/test.key

second_test_crt:
  x509.certificate_managed:
    - name: {{ tmp_dir  }}/pki/test.crt
    - ca_server: minion
    - signing_policy: ca_policy
    - public_key: {{ tmp_dir  }}/pki/test.key
    - CN: minion
    - days_remaining: 30
    - backup: True
    - require:
        - x509: {{ tmp_dir  }}/pki/ca.crt
        - x509: {{ tmp_dir  }}/pki/test.key
        - x509: {{ tmp_dir  }}/pki/test.crt
