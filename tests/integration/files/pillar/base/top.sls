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
  'N@mins not L@minion':
    - ng1
  'N@missing_minion':
    - ng2
