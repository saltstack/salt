A:
  cmd.run:
    - name: echo A
    - require:
      - cmd: B

B:
  cmd.run:
    - name: echo B
    - require:
      - cmd: A

