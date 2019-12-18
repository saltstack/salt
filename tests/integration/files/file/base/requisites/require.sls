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

A:
  cmd.run:
    - name: echo A fifth
    - require:
      - cmd: C
B:
  cmd.run:
    - name: echo B second
    - require_in:
      - cmd: A
      - cmd: C

C:
  cmd.run:
    - name: echo C third

D:
  cmd.run:
    - name: echo D first
    - require_in:
      - cmd: B

E:
  cmd.run:
    - name: echo E fourth
    - require:
      - cmd: B
    - require_in:
      - cmd: A

# will fail with "The following requisites were not found"
F:
  cmd.run:
    - name: echo F
    - require:
      - foobar: A
# will fail with "The following requisites were not found"
G:
  cmd.run:
    - name: echo G
    - require:
      - cmd: Z
# will fail with "The following requisites were not found"
H:
  cmd.run:
    - name: echo H
    - require:
      - cmd: Z

