# Complex require/require_in graph, using use for some require
# issue #8796: use does not inherit require
#
# C (0) <====+ <===========+ <===+
#            |             |     |
# A (1) ==u==+             |     |
#                          |     |
# E (3) <============+     |     |
#                    |     |     |
# F (3) <=======+    |     |     |
#               |    |     |     |
# B (4) <==+ =u=+ =r=+ ==r=+     |
#          |                     |
# D (5) =r=+ =r==================+

A:
  cmd.run:
    - name: echo A
    - use:
      - cmd: D
    # TODO: should be inherited and removed
    - require:
      - cmd: C

B:
  cmd.run:
    - name: echo B
    - require_in:
      - cmd: D
    - use:
      - cmd: D
    # TODO: should be inherited and removed
    - require:
      - cmd: C
C:
  cmd.run:
    - name: echo C

D:
  cmd.run:
    - name: echo D
    - require:
      - cmd: C

E:
  cmd.run:
    - name: echo E
    - require_in:
      - cmd: B

F:
  cmd.run:
    - name: echo F
    - use:
      - cmd: E
    # TODO: should be inherited and removed
    - require_in:
      - cmd: B
