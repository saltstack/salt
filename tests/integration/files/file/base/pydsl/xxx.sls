#!stateconf -os yaml . jinja
include:
  - pydsl.yyy
extend:
  pydsl.yyy::start:
    stateconf.set:
      - require:
        - stateconf: .goal
  pydsl.yyy::Y1:
    cmd.run:
      - name: 'echo Y1 extended >> /tmp/output'
.X1:
  cmd.run:
    - name: echo X1 >> /tmp/output
    - cwd: /
.X2:
  cmd.run:
    - name: echo X2 >> /tmp/output
    - cwd: /
.X3:
  cmd.run:
    - name: echo X3 >> /tmp/output
    - cwd: /
