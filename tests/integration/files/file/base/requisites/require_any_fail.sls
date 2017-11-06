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

# A should fail since both E & F fail
D:
  cmd.run:
    - name: echo D
    - require_any:
      - cmd: E
      - cmd: F
      - cmd: G
E:
  cmd.run:
    - name: 'false'

F:
  cmd.run:
    - name: 'false'

G:
  cmd.run:
    - name: 'false'
