a:
  cmd.run:
    - name: exit 0

b:
  cmd.run:
    - name: exit 1

c:
  cmd.run:
    - name: exit 0

d:
  cmd.run:
    - name: echo itworked
    - onfail_any:
      - cmd: a
      - cmd: b
      - cmd: c

e:
  cmd.run:
    - name: exit 0

f:
  cmd.run:
    - name: exit 0

g:
  cmd.run:
    - name: exit 0

h:
  cmd.run:
    - name: echo itworked
    - onfail_any:
      - cmd: e
      - cmd: f
      - cmd: g
