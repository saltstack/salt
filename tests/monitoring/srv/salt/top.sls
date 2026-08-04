base:
  '*':
    - heavy.jinja
    - heavy.many_files
    - heavy.cmd
  'salt-minion-1':
    - loadbalancer
  'salt-minion-2':
    - webserver
  'salt-minion-3':
    - webserver
