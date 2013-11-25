A:
  cmd.run:
    - name: echo A
B:
  cmd.run:
    - name: echo B
    # here used without "-"
    - require:
        cmd: A
C:
  cmd.run:
    - name: echo C
    # here used without "-"
    - require_in:
        cmd: A
