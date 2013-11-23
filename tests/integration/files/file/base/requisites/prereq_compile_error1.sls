A:
  cmd.run:
    - name: echo A

B:
  cmd.run:
    - name: echo B
    - prereq:
      - foobar: A

