a:
  cmd.run:
    - name: exit 1

pass:
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

e:
  cmd.run:
    - name: echo e
    - onfail:
      - cmd: pass
    - require:
      - cmd: c

f:
  cmd.run:
    - name: echo f
    - onfail:
      - cmd: pass
    - onchanges:
      - cmd: b
