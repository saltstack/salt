{% set tmp_dir = pillar['tmp_dir'] %}

{{ tmp_dir }}/pki:
  file.directory

{{ tmp_dir  }}/pki/issued_certs:
  file.directory

{{ tmp_dir  }}/pki/ca.key:
  x509.private_key_managed:
    - bits: 4096
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
    - managed_private_key:
        name: {{ tmp_dir  }}/pki/ca.key
        bits: 4096
        backup: True
    - require:
      - file: {{ tmp_dir  }}/pki
      - {{ tmp_dir  }}/pki/ca.key

mine.send:
  module.run:
    - func: x509.get_pem_entries
    - kwargs:
        glob_path: {{ tmp_dir  }}/pki/ca.crt
    - onchanges:
      - x509: {{ tmp_dir  }}/pki/ca.crt

test_priv_key:
  x509.private_key_managed:
    - name: {{ pillar['keyfile'] }}
    - bits: 4096

test_crt:
  x509.certificate_managed:
    - name: {{ pillar['crtfile'] }}
    - public_key: {{ pillar['keyfile'] }}
    - ca_server: minion
    - signing_policy: ca_policy
    - CN: minion
    - days_remaining: 30
    - backup: True
    - require:
        - {{ tmp_dir  }}/pki/ca.crt
        - test_priv_key
