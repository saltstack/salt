A:
  cmd.run:
    - name: echo A
    - prereq_in:
      - cmd: B
B:
  cmd.run:
    - name: echo B
    - prereq_in:
      - cmd: A
