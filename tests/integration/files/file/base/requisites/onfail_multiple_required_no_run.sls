a:
  cmd.run:
    - name: exit 0

b:
  cmd.run:
    - name: echo b
    - onfail:
      - cmd: a

c:
  cmd.run:
    - name: echo c
    - onfail:
      - cmd: a
    - require:
      - cmd: b

d:
  cmd.run:
    - name: echo d
    - onfail:
      - cmd: a
    - require:
      - cmd: c
