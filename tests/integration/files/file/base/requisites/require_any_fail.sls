# D should fail since both E & F fail
E:
  cmd.run:
    - name: 'false'

F:
  cmd.run:
    - name: 'false'

D:
  cmd.run:
    - name: echo D
    - require_any:
      - cmd: E
      - cmd: F
