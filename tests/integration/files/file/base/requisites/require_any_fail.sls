# A should fail since both E & F fail
D:
  cmd.run:
    - name: echo D
    - require_any:
      - cmd: E
      - cmd: F

E:
  cmd.run:
    - name: 'false'

F:
  cmd.run:
    - name: 'false'
