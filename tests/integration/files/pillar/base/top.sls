base:
  'minion':
    - generic
    - sdb
    - include
    - glob_include
    - packagingtest
    - include-c
    - include-d
  'sub_minion':
    - sdb
    - generic
    - sub
  'localhost':
    - generic
