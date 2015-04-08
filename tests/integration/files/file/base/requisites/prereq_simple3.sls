# A --+
#     |
# B <-+ ----+
#           |
# C <-------+

# runs before A and/or B
A:
  cmd.run:
    - name: echo A first
    # is running in test mode before B/C
    - prereq:
      - cmd: B
      - cmd: C

# always has to run
B:
  cmd.run:
    - name: echo B second

# never has to run
C:
  cmd.wait:
    - name: echo C third
