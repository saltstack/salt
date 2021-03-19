# Complex require/require_in graph
#
# Relative order of C>E is given by the definition order
#
# D (1) <--+
#          |
# B (2) ---+ <-+ <-+ <-+
#              |   |   |
# C (3) <--+ --|---|---+
#          |   |   |
# E (4) ---|---|---+ <-+
#          |   |       |
# A (5) ---+ --+ ------+
#

# A should success since B succeeds even though C fails.
A:
  cmd.run:
    - name: echo A
    - require_any:
      - cmd: B
      - cmd: C
      - cmd: D
B:
  cmd.run:
    - name: echo B

C:
  cmd.run:
    - name: "$(which false)"

D:
  cmd.run:
    - name: echo D 
