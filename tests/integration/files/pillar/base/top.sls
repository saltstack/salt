base:
  'minion':
    - generic
    - sdb
    - include
    - glob_include
  'sub_minion':
    - sdb
    - generic
    - sub
  'localhost':
    - generic
