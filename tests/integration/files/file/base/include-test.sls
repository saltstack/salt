include:
  - to-include-test

{{ pillar['include-test'] }}:
  file.managed:
    - source: salt://testfile
