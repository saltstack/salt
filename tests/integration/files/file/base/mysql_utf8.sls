# -*- coding: utf-8 -*-
#
# We all agree that a real world example would take credentials from pillar
# this is simply an utf-8 test
A:
  mysql_database.present:
    - name: "foo 準`bar"
    - character_set: utf8
    - collate: utf8_general_ci
    - connection_user: root
    - connection_pass: poney
    - connection_use_unicode: True
    - connection_charset: utf8
    - saltenv:
        - LC_ALL: "en_US.utf8"
B:
  mysql_database.absent:
    - name: "foo 準`bar"
    - character_set: utf8
    - collate: utf8_general_ci
    - connection_user: root
    - connection_pass: poney
    - connection_use_unicode: True
    - connection_charset: utf8
    - saltenv:
        - LC_ALL: "en_US.utf8"
    - require:
        - mysql_database: A

