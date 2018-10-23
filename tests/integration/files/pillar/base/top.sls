base:
  'minion':
    - generic
    - blackout
    - sdb
  'sub_minion':
    - sdb
    - generic
    - blackout
    - sub
  'localhost':
    - generic
    - blackout
