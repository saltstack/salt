exclude:
  - to-include-test

include:
  - include-test

{{ pillar['exclude-test'] }}:
  file.managed:
    - source: salt://testfile
