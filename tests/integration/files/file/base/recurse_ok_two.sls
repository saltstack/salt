nagios-nrpe-server:
  pkg:
    - installed
  service:
    - running
    - watch:
      - file: /etc/nagios/nrpe.cfg

/etc/nagios/nrpe.cfg:
  file:
    - managed
    - source: salt://baseserver/nrpe.cfg
    - require:
      - pkg: nagios-nrpe-server

