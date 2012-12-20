/etc/foobar:
  file.recurse:
    - source: salt://fuzz/
  file.managed:
    - source: salt://fuzz/multi_state.sls
