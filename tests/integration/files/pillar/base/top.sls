base:
  'minion':
    - generic
    - blackout
    - sdb
    - include
    - glob_include
  'sub_minion':
    - sdb
    - generic
    - blackout
    - sub
  'localhost':
    - generic
    - blackout
