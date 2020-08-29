base:
  'minion':
    - generic
    - sdb
    - include
    - glob_include
    - packagingtest
  'sub_minion':
    - sdb
    - generic
    - sub
  'localhost':
    - generic
