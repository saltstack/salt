a:
  cmd.run:
    - name: exit 0

b:
  cmd.run:
    - name: exit 0

c:
  cmd.run:
    - name: exit 0

d:
  cmd.run:
    - name: exit 1

e:
  cmd.run:
    - name: exit 1

f:
  cmd.run:
    - name: exit 1

reqs not met:
  cmd.run:
    - name: echo itdidntonfail
    - onfail_all:
      - cmd: a
      - cmd: e

reqs also not met:
  cmd.run:
    - name: echo italsodidnonfail
    - onfail_all:
      - cmd: a
      - cmd: b
      - cmd: c

reqs met:
  cmd.run:
    - name: echo itonfailed
    - onfail_all:
      - cmd: d
      - cmd: e
      - cmd: f

reqs also met:
  cmd.run:
    - name: echo itonfailed
    - onfail_all:
      - cmd: d
    - require:
      - cmd: a
