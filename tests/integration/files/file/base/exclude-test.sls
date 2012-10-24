exclude:
  - to-include-test

include:
  - include-test

/tmp/exclude-test:
  file:
    - managed
    - source: salt://testfile
