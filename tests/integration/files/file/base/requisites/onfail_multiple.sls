a:
  cmd.run:
    - name: exit 0

b:
  cmd.run:
    - name: exit 1

c:
  cmd.run:
    - name: echo itworked
    - onfail:
      - cmd: a
      - cmd: b
