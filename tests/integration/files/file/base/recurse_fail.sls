mysql:
  service:
    - running
    - require:
      - file: /etc/mysql/my.cnf

/etc/mysql/my.cnf:
  file:
    - managed
    - source: salt://master.cnf
    - require:
      - service: mysql

