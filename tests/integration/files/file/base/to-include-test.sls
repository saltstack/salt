{{ pillar['to-include-test'] }}:
  file.managed:
    - source: salt://testfile
