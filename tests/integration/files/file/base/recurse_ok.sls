snmpd:
  pkg:
    - installed
  service:
    - running
    - require:
      - pkg: snmpd
    - watch:
      - file: /etc/snmp/snmpd.conf

/etc/snmp/snmpd.conf:
  file:
    - managed
    - source: salt://snmpd/snmpd.conf.jinja
    - template: jinja
    - user: root
    - group: root
    - mode: "0600"
    - require:
      - pkg: snmpd

